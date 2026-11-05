"""Dixon-Coles 模型（生产移植 · 与 W1 回测同参）。

- 强度：xG 指数衰减（半衰期 180d，窗口 540d），每队 attack/defense
- 预测：泊松网格 0..10 + DC tau 调整（rho = -0.06）
- 保真度验证：tests/test_dc_model.py 对 2023-24 英超 backtest，
  log loss 应接近 W1 结果 0.9191（断言 < 0.95）

数据：w1-validation/xg_matches.csv（10,707 场 Understat xG，2019-2025 五大联赛）。
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


@dataclass
class DCPrediction:
    p_home: float
    p_draw: float
    p_away: float
    lambda_home: float
    lambda_away: float


@dataclass
class DCModel:
    """拟合好的强度表。keys 为归一化队名（含规范中文键）。"""
    as_of: datetime
    halflife_days: int = 180
    window_days: int = 540
    rho: float = -0.06
    min_matches: int = 3
    attack: dict[str, float] = field(default_factory=dict)
    defense: dict[str, float] = field(default_factory=dict)
    mu_half: float = 1.35          # 每队期望进球基准（(xg_h+xg_a)/2 的加权均值）
    home_adv: float = 1.15         # 主场系数（加权 xg_home / xg_away）
    teams: set[str] = field(default_factory=set)
    source: str = "xg"             # xg / goals_proxy（证据层必须如实标注）


GRID = np.arange(0, 11)


_COL_ALIASES = {
    "datetime": ("datetime", "date_time", "date", "match_date", "time"),
    "team_home": ("team_home", "home_team", "h_team", "home", "h"),
    "team_away": ("team_away", "away_team", "a_team", "away", "a"),
    "xg_home": ("xg_home", "xg_h", "hxg", "h_xg"),
    "xg_away": ("xg_away", "xg_a", "axg", "a_xg"),
    "goals_home": ("goals_home", "score_h", "fthg", "gh"),
    "goals_away": ("goals_away", "score_a", "ftag", "ga"),
}


def _pick_col(cols: set[str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def load_xg(path: str, extra_dir: str = "") -> pd.DataFrame:
    """加载主 csv + dumps 目录全部 csv，列名自适应映射（W1 schema / understat raw 均可）。

    主 schema 为准（W1: understat_id,datetime,team_home,...）；映射不齐的文件跳过。
    """
    import glob

    frames = []
    paths = [path]
    if extra_dir and os.path.isdir(extra_dir):
        paths += sorted(glob.glob(os.path.join(extra_dir, "*.csv")))
    for p in paths:
        if not p or not os.path.exists(p) or os.path.getsize(p) < 50:
            continue
        try:
            df = pd.read_csv(p, low_memory=False)
        except Exception:
            continue
        lower = {c.lower().strip(): c for c in df.columns}
        cols = set(lower.keys())
        c_dt = _pick_col(cols, _COL_ALIASES["datetime"])
        c_h = _pick_col(cols, _COL_ALIASES["team_home"])
        c_a = _pick_col(cols, _COL_ALIASES["team_away"])
        c_xh = _pick_col(cols, _COL_ALIASES["xg_home"])
        c_xa = _pick_col(cols, _COL_ALIASES["xg_away"])
        if not all([c_dt, c_h, c_a, c_xh, c_xa]):
            continue
        sub = df.rename(columns={lower[c_dt]: "datetime", lower[c_h]: "team_home",
                                 lower[c_a]: "team_away", lower[c_xh]: "xg_home",
                                 lower[c_xa]: "xg_away"})
        try:
            sub["xg_home"] = pd.to_numeric(sub["xg_home"], errors="coerce")
            sub["xg_away"] = pd.to_numeric(sub["xg_away"], errors="coerce")
        except Exception:
            continue
        sub = sub.dropna(subset=["xg_home", "xg_away"])
        keep = ["datetime", "team_home", "team_away", "xg_home", "xg_away"]
        for gc, cands in (("goals_home", _COL_ALIASES["goals_home"]),
                          ("goals_away", _COL_ALIASES["goals_away"])):
            c = _pick_col(cols, cands)
            if c:
                sub[gc] = pd.to_numeric(df[lower[c]], errors="coerce")
                keep.append(gc)
        frames.append(sub[keep])
    if not frames:
        raise ValueError(f"no usable xG csv under {path!r} / {extra_dir!r}")
    out = pd.concat(frames, ignore_index=True)
    # 去重：同日同对阵保留一条（dumps 与主 csv 可能有重叠）
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    out = out.dropna(subset=["datetime"])
    out = out.drop_duplicates(subset=["datetime", "team_home", "team_away"])
    return out


def _weights(dates: pd.Series, as_of: datetime, halflife: int, window: int) -> np.ndarray:
    age = (as_of - dates).dt.total_seconds() / 86400.0
    w = np.exp(-math.log(2.0) * age / halflife)
    w[age > window] = 0.0
    w[age < 0] = 0.0  # 未来场次不参与
    return w.values


def fit(xg_df: pd.DataFrame, as_of: datetime, halflife_days: int = 180,
        window_days: int = 540, rho: float = -0.06, min_matches: int = 3) -> DCModel:
    """从 Understat xG 场次表拟合强度。列：datetime, team_home, team_away, xg_home, xg_away。"""
    df = xg_df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df[df["datetime"] <= pd.Timestamp(as_of)]
    w = _weights(df["datetime"], as_of, halflife_days, window_days)
    df = df.assign(_w=w)
    df = df[df["_w"] > 0]
    if df.empty:
        raise ValueError("no xG data inside decay window")

    mu_half = float((df["_w"] * (df["xg_home"] + df["xg_away"]) / 2).sum() / df["_w"].sum())
    home_adv = float((df["_w"] * df["xg_home"]).sum() / (df["_w"] * df["xg_away"]).sum())

    model = DCModel(as_of=as_of, halflife_days=halflife_days, window_days=window_days,
                    rho=rho, min_matches=min_matches, mu_half=mu_half, home_adv=home_adv)

    # 各队加权 xG 进/失
    home_g = df.groupby("team_home").apply(
        lambda g: (g["_w"] * g["xg_home"]).sum() / g["_w"].sum(), include_groups=False)
    home_concede = df.groupby("team_home").apply(
        lambda g: (g["_w"] * g["xg_away"]).sum() / g["_w"].sum(), include_groups=False)
    away_g = df.groupby("team_away").apply(
        lambda g: (g["_w"] * g["xg_away"]).sum() / g["_w"].sum(), include_groups=False)
    away_concede = df.groupby("team_away").apply(
        lambda g: (g["_w"] * g["xg_home"]).sum() / g["_w"].sum(), include_groups=False)
    counts = df["team_home"].value_counts().add(df["team_away"].value_counts(), fill_value=0)

    # 规范化：attack/defense 以联赛加权均值为 1
    att_raw = pd.concat([home_g, away_g], axis=1).mean(axis=1)
    def_raw = pd.concat([home_concede, away_concede], axis=1).mean(axis=1)
    att_mean = float(att_raw.mean())
    def_mean = float(def_raw.mean())

    for team in att_raw.index:
        if counts.get(team, 0) < min_matches:
            continue
        model.attack[team] = att_raw[team] / att_mean
        model.defense[team] = def_raw[team] / def_mean
        model.teams.add(team)
    if not model.attack:
        raise ValueError("no team reached min_matches in window")
    return model


def add_alias(model: DCModel, alias: str, canonical: str) -> None:
    """为规范中文队名建立强度键（ingest 对齐后用 canonical 查模型）。"""
    a, d = model.attack.get(alias), model.defense.get(alias)
    if a is not None and d is not None and canonical not in model.attack:
        model.attack[canonical] = a
        model.defense[canonical] = d
        model.teams.add(canonical)


def _tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1.0 - lh * la * rho
    if x == 0 and y == 1:
        return 1.0 + lh * rho
    if x == 1 and y == 0:
        return 1.0 + la * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def predict(model: DCModel, home: str, away: str) -> DCPrediction | None:
    """1x2 预测。任一队不在强度表 → None（模闸 pending_data）。"""
    params = _params(model, home, away)
    if params is None:
        return None
    ah, dh, aa, da = params
    lh = float(np.clip(ah * da * model.home_adv * model.mu_half, 0.05, 6.0))
    la = float(np.clip(aa * dh * model.mu_half, 0.05, 6.0))
    ph, pd_, pa, mat = _grid_probs(lh, la, model.rho)
    return DCPrediction(ph, pd_, pa, lh, la)


def _params(model: DCModel, home: str, away: str):
    ah, dh = model.attack.get(home), model.defense.get(home)
    aa, da = model.attack.get(away), model.defense.get(away)
    if ah is None or dh is None or aa is None or da is None:
        return None
    return ah, dh, aa, da


def _grid_probs(lh: float, la: float, rho: float):
    """泊松网格 + DC tau → (p_home, p_draw, p_away, matrix)。"""
    ph = np.exp(-lh) * np.power(lh, GRID) / np.array([math.factorial(k) for k in GRID])
    pa = np.exp(-la) * np.power(la, GRID) / np.array([math.factorial(k) for k in GRID])
    mat = np.outer(ph, pa)
    for x in range(len(GRID)):
        for y in range(len(GRID)):
            mat[x, y] *= _tau(x, y, lh, la, rho)
    mat = np.clip(mat, 0, None)
    mat /= mat.sum()
    return float(np.tril(mat, -1).sum()), float(np.trace(mat)), float(np.triu(mat, 1).sum()), mat


def predict_line(model: DCModel, home: str, away: str, line_val: float) -> DCPrediction | None:
    """让球口径预测：调整后净胜球 = 主队进球 − 客队进球 + line_val。

    line_val 取竞彩 goal_line（如 "-1" → 主队让 1 球 → adj = x − y − 1）。
    返回（让球主胜, 让平, 让客胜）三元概率；λ 字段保留基础口径供证据展示。
    """
    params = _params(model, home, away)
    if params is None:
        return None
    ah, dh, aa, da = params
    lh = float(np.clip(ah * da * model.home_adv * model.mu_half, 0.05, 6.0))
    la = float(np.clip(aa * dh * model.mu_half, 0.05, 6.0))
    _, _, _, mat = _grid_probs(lh, la, model.rho)
    xs = GRID.reshape(-1, 1)
    ys = GRID.reshape(1, -1)
    adj = xs - ys + line_val
    p_home = float(mat[adj > 0].sum())
    p_draw = float(mat[adj == 0].sum())
    p_away = float(mat[adj < 0].sum())
    return DCPrediction(p_home, p_draw, p_away, lh, la)


def backtest_logloss(xg_df: pd.DataFrame, **kw) -> float:
    """留一日回测（expanding，无未来信息），返回 3 类 log loss —— 移植保真度检查用。"""
    df = xg_df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    if df.empty:
        raise ValueError("empty backtest frame")
    losses, n = [], 0
    day = df["datetime"].dt.date
    for d in sorted(day.unique()):
        test = df[day == d]
        train_hist = df[day < d]
        if train_hist.empty:
            continue
        try:
            m = fit(train_hist, as_of=pd.Timestamp(d).to_pydatetime() + timedelta(hours=12), **kw)
        except ValueError:
            continue  # 早期历史不足以拟合（<min_matches），跳过该日
        for r in test.itertuples(index=False):
            if r.team_home not in m.attack or r.team_away not in m.attack:
                continue
            p = predict(m, r.team_home, r.team_away)
            if p is None:
                continue
            actual = 0 if r.goals_home > r.goals_away else (1 if r.goals_home == r.goals_away else 2)
            probs = [p.p_home, p.p_draw, p.p_away]
            losses.append(-math.log(max(probs[actual], 1e-12)))
            n += 1
    if not losses:
        raise ValueError("backtest produced no predictions")
    return float(np.mean(losses))
