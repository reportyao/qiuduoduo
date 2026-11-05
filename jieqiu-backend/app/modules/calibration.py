"""概率区间：按置信分桶的经验残差区间。

样本足够时，用已结算 promoted 判决的 (实际结果 - 预测概率) 残差分位构造区间；
样本不足时明确返回 accumulating，不伪造“精确区间”。这是公开契约 prob_low/high
的唯一来源，后台/前端都不得自己编。
"""
from __future__ import annotations

import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Verdict

_CACHE: dict[str, tuple[float, dict[int, list[float]]]] = {}
_LOCK = threading.Lock()
_TTL = 300.0
MIN_SAMPLES = 20


def _bucket(prob: float) -> int:
    return max(0, min(9, int(float(prob) * 10)))


def _load(db: Session) -> dict[int, list[float]]:
    rows = db.scalars(
        select(Verdict).where(Verdict.status == "promoted",
                              Verdict.settled.isnot(None))
        .order_by(Verdict.settled_at.desc()).limit(1000)).all()
    buckets: dict[int, list[float]] = {}
    for v in rows:
        if v.settled not in ("win", "lose"):
            continue
        prob = (v.pick or {}).get("prob")
        if not isinstance(prob, (int, float)):
            continue
        actual = 1.0 if v.settled == "win" else 0.0
        buckets.setdefault(_bucket(float(prob)), []).append(actual - float(prob))
    return buckets


def _buckets(db: Session) -> dict[int, list[float]]:
    if get_settings().env == "test":
        return _load(db)
    with _LOCK:
        cached = _CACHE.get("all")
    if cached and (time.time() - cached[0]) < _TTL:
        return cached[1]
    data = _load(db)
    with _LOCK:
        _CACHE["all"] = (time.time(), data)
    return data


def _interval_from_values(prob: float, values: list[float]) -> tuple[float | None, float | None]:
    if len(values) < MIN_SAMPLES:
        return None, None
    ordered = sorted(values)
    q10 = ordered[int((len(ordered) - 1) * 0.10)]
    q90 = ordered[int((len(ordered) - 1) * 0.90)]
    return (round(max(0.0, prob + q10), 4),
            round(min(1.0, prob + q90), 4))


def interval(db: Session, prob: float | None) -> tuple[float | None, float | None, str, int, str]:
    """返回 (low, high, status, n, method)。status: ok / accumulating / no_confidence。"""
    if prob is None:
        return None, None, "no_confidence", 0, "empirical_residual_v1"
    buckets = _buckets(db)
    values = buckets.get(_bucket(float(prob)), [])
    low, high = _interval_from_values(float(prob), values)
    if low is None:
        return None, None, "accumulating", len(values), "empirical_residual_v1"
    return low, high, "ok", len(values), "empirical_residual_v1"


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
