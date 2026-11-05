"""历史赛果兜底：为 DC 模型补一份“进球代理”数据。

背景：静态 `xg_matches.csv` 只到 2024-25；Understat 对云服务器返回挑战页，
`penaltyblog` 解析失败。模型闸因此长期 pending_data，推荐主链无法产出 published。

本模块从 football-data.co.uk 下载五大联赛历史比分，写成 dc_model 可读的
`xg_home/xg_away`（用进球数代理 xG），文件名带 `footballdata_` 前缀。
它是**兜底**，不是真 xG：`verdict` 会在证据里标注来源，模型置信门仍按原阈值。
"""
from __future__ import annotations

import io
import os
import tempfile
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from ..config import get_settings

LEAGUES = {
    "E0": "EPL",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}
_THROTTLE_FILE = os.path.join(tempfile.gettempdir(), "jq_results_xg_last_sync")
_BASE = "https://www.football-data.co.uk/mmz4281"


def _season_codes(now: datetime) -> list[str]:
    """当前赛季 + 上赛季的 mmz4281 目录名（如 2026-11 → 2627, 2526）。"""
    y = now.year
    # 8 月以后算新赛季；1–7 月仍属上一赛季
    start = y if now.month >= 8 else y - 1
    return [f"{str(start)[2:]}{str(start + 1)[2:]}",
            f"{str(start - 1)[2:]}{str(start)[2:]}"]


def _throttled(now: datetime) -> bool:
    try:
        if os.path.exists(_THROTTLE_FILE):
            last = datetime.fromisoformat(open(_THROTTLE_FILE).read().strip())
            if (now - last).total_seconds() < 24 * 3600:
                return True
    except Exception:
        pass
    return False


def _mark(now: datetime) -> None:
    try:
        with open(_THROTTLE_FILE, "w") as f:
            f.write(now.isoformat())
    except OSError:
        pass


def _parse_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), low_memory=False)
    cols = {c.strip().lower(): c for c in df.columns}
    need = [cols.get(x) for x in ("date", "hometeam", "awayteam", "fthg", "ftag")]
    if not all(need):
        raise ValueError("football-data csv 缺列")
    out = pd.DataFrame({
        "datetime": pd.to_datetime(df[need[0]], dayfirst=True, errors="coerce")
        .dt.strftime("%Y-%m-%d %H:%M:%S"),
        "team_home": df[need[1]].astype(str),
        "team_away": df[need[2]].astype(str),
        "goals_home": pd.to_numeric(df[need[3]], errors="coerce"),
        "goals_away": pd.to_numeric(df[need[4]], errors="coerce"),
    }).dropna(subset=["datetime", "goals_home", "goals_away"])
    # 用进球代理 xG；dc_model 只要求 xg_home/xg_away 两列。
    out["xg_home"] = out["goals_home"]
    out["xg_away"] = out["goals_away"]
    return out[["datetime", "team_home", "team_away", "xg_home", "xg_away",
                "goals_home", "goals_away"]]


def sync_results_xg(now: datetime | None = None, fetcher=None) -> tuple[int, str]:
    """下载并落档历史比分；返回 (新增文件数, 说明)。失败不抛错。"""
    st = get_settings()
    now = now or datetime.now(timezone.utc)
    out_dir = getattr(st, "xg_extra_dir", "") or os.path.join(
        os.path.dirname(st.xg_data_path or "."), "xg_dumps")
    os.makedirs(out_dir, exist_ok=True)
    if _throttled(now):
        return 0, "节流：距上次尝试不足 24h，跳过"

    if fetcher is None:
        def fetcher(code: str, season: str) -> bytes:
            url = f"{_BASE}/{season}/{code}.csv"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()

    written = 0
    notes: list[str] = []
    for season in _season_codes(now):
        for code, tag in LEAGUES.items():
            path = os.path.join(out_dir, f"footballdata_{code}_{season}.csv")
            if os.path.exists(path) and os.path.getsize(path) > 2000:
                continue
            try:
                df = _parse_csv(fetcher(code, season))
                if df.empty:
                    continue
                df.to_csv(path, index=False)
                written += 1
                notes.append(f"{tag}/{season}:{len(df)}")
            except Exception as exc:  # noqa: BLE001 - 单联赛失败不阻断
                notes.append(f"{tag}/{season}:{type(exc).__name__}")
    _mark(now)
    if not written:
        return 0, "赛果兜底不可用（" + "; ".join(notes[:3]) + "…）"
    return written, "新落档 " + "; ".join(notes)


def has_results_proxy(extra_dir: str) -> bool:
    return bool(extra_dir and os.path.isdir(extra_dir) and any(
        name.startswith("footballdata_") and name.endswith(".csv")
        for name in os.listdir(extra_dir)))
