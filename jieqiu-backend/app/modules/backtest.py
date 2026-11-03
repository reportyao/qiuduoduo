"""校准 + 回测框架（W4 数据流）。

evaluate(): 滚动留一日回测 → log loss / 命中率 / 10 桶校准（预测置信 vs 实际频率）
结果入 model_evals 表，/model/evals 可查。CLI：python -m app.backtest
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..config import get_settings
from .dc_model import fit, load_xg, predict
from ..models import ModelEval


def evaluate(df: pd.DataFrame, as_of_start: str, as_of_end: str,
             **dc_kw) -> dict:
    """留一日 expanding 回测 + 校准分桶。df 需含 datetime/team_home/team_away/xg_*/goals_*。"""
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    day = df["datetime"].dt.date
    start = pd.Timestamp(as_of_start).date()
    end = pd.Timestamp(as_of_end).date()

    losses, hits, n = [], 0, 0
    buckets: dict[int, list[int]] = {i: [0, 0] for i in range(10)}  # [predicted_sum_hits? -> (sum_pred, n, sum_actual)]
    cal = {i: [0.0, 0, 0] for i in range(10)}  # sum_pred, n, sum_actual

    for d in sorted({x for x in day.unique() if start <= x <= end}):
        test = df[day == d]
        hist = df[day < d]
        if hist.empty:
            continue
        try:
            m = fit(hist, as_of=pd.Timestamp(d).to_pydatetime() + pd.Timedelta(hours=12), **dc_kw)
        except ValueError:
            continue
        for r in test.itertuples(index=False):
            p = predict(m, r.team_home, r.team_away)
            if p is None:
                continue
            actual = 0 if r.goals_home > r.goals_away else (1 if r.goals_home == r.goals_away else 2)
            probs = [p.p_home, p.p_draw, p.p_away]
            losses.append(-math.log(max(probs[actual], 1e-12)))
            top_i = int(np.argmax(probs))
            if top_i == actual:
                hits += 1
            n += 1
            b = min(9, int(probs[top_i] * 10))
            cal[b][0] += probs[top_i]
            cal[b][1] += 1
            cal[b][2] += 1 if top_i == actual else 0

    if n == 0:
        raise ValueError("no predictions in evaluation window")
    calibration = []
    for b in sorted(cal):
        s, cnt, a = cal[b]
        if cnt == 0:
            continue
        calibration.append({
            "bucket": f"{b*10}-{(b+1)*10}%",
            "n": cnt,
            "mean_predicted": round(s / cnt, 4),
            "observed_freq": round(a / cnt, 4),
        })
    return {
        "n": n,
        "logloss": round(float(np.mean(losses)), 4),
        "accuracy": round(hits / n, 4),
        "calibration": calibration,
        "params": {k: v for k, v in dc_kw.items()} | {"window": [as_of_start, as_of_end]},
    }


def run_and_store(db: Session, label: str, as_of_start: str, as_of_end: str, **dc_kw) -> ModelEval:
    st = get_settings()
    df = load_xg(st.xg_data_path, st.xg_extra_dir)
    metrics = evaluate(df, as_of_start, as_of_end, **dc_kw)
    ev = ModelEval(label=label, params=metrics["params"], metrics=metrics)
    db.add(ev)
    db.commit()
    return ev
