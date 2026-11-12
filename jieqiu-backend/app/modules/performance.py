"""用户可见战绩读模型：单场推荐摘要 / 近期明细。

只统计 `DecisionSnapshot.status=published` + `Verdict.settled`。
没有数据返回 None，前端不硬写“昨天 3 中 2”。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DecisionSnapshot, PerformanceDaily, Verdict, utcnow
from .timeutil import CN, trade_date_now


def _latest_published(db: Session, start: str, end: str) -> list[tuple[DecisionSnapshot, Verdict]]:
    rows = db.execute(
        select(DecisionSnapshot, Verdict)
        .join(Verdict, DecisionSnapshot.verdict_id == Verdict.id)
        .where(DecisionSnapshot.status == "published",
               DecisionSnapshot.trade_date >= start,
               DecisionSnapshot.trade_date <= end)
        .order_by(DecisionSnapshot.trade_date.desc(), DecisionSnapshot.version.desc())
    ).all()
    # 同一场同一天只取最新 published 版本，避免多版本重复计数。
    chosen: dict[tuple[str, str], tuple[DecisionSnapshot, Verdict]] = {}
    for snap, verdict in rows:
        key = (snap.trade_date, snap.match_id)
        chosen.setdefault(key, (snap, verdict))
    return list(chosen.values())


def _unit_pnl(v: Verdict) -> float:
    if v.settled == "win":
        try:
            return float((v.pick or {}).get("sp") or 0) - 1.0
        except (TypeError, ValueError):
            return 0.0
    if v.settled == "lose":
        return -1.0
    return 0.0


def record_summary(db: Session, days: int = 30) -> dict | None:
    days = max(1, min(int(days), 180))
    today = datetime.strptime(trade_date_now(), "%Y-%m-%d")
    start = (today - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    rows = _latest_published(db, start, end)
    if not rows:
        return None
    settled = [(s, v) for s, v in rows if v.settled in ("win", "lose")]
    wins = sum(1 for _, v in settled if v.settled == "win")
    hit_days = len({s.trade_date for s, v in settled if v.settled == "win"})
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    y_rows = [(s, v) for s, v in rows if s.trade_date == yesterday]
    y_settled = [(s, v) for s, v in y_rows if v.settled in ("win", "lose")]
    return {
        "yesterday": ({
            "picks": len(y_rows),
            "settled": len(y_settled),
            "hits": sum(1 for _, v in y_settled if v.settled == "win"),
        } if y_rows else None),
        "last_30_days": {
            "days": days,
            "picks": len(rows),
            "settled": len(settled),
            "hits": wins,
            "hit_days": hit_days,
        },
        "recent": [{
            "verdict_id": v.id,
            "match_id": v.match_id,
            "trade_date": v.trade_date,
            "league": v.league,
            "home": v.home,
            "away": v.away,
            "pick": (v.pick or {}).get("dir"),
            "odds": (v.pick or {}).get("sp"),
            "settled": v.settled,
            "score": v.result_score,
            "clv": v.clv,
        } for _, v in sorted(rows, key=lambda x: (x[0].trade_date, x[0].match_id),
                             reverse=True)[:20]],
    }


def rebuild_ai_record_daily(db: Session, days: int = 90) -> int:
    """把近 N 天单场战绩写入 performance_daily。"""
    today = datetime.strptime(trade_date_now(), "%Y-%m-%d")
    start = (today - timedelta(days=max(1, days) - 1)).strftime("%Y-%m-%d")
    rows = _latest_published(db, start, today.strftime("%Y-%m-%d"))
    if not rows:
        return 0
    by_day: dict[str, list[Verdict]] = {}
    for snap, v in rows:
        by_day.setdefault(snap.trade_date, []).append(v)
    n = 0
    for day, items in by_day.items():
        settled = [v for v in items if v.settled in ("win", "lose")]
        wins = sum(1 for v in settled if v.settled == "win")
        pnl = sum(_unit_pnl(v) for v in settled)
        row = db.scalar(select(PerformanceDaily).where(
            PerformanceDaily.scope == "ai_record",
            PerformanceDaily.trade_date == day,
            PerformanceDaily.risk_level == "",
            PerformanceDaily.market == "",
        ))
        if row is None:
            row = PerformanceDaily(scope="ai_record", trade_date=day,
                                   risk_level="", market="")
            db.add(row)
        row.picks = len(items)
        row.wins = wins
        row.losses = len(settled) - wins
        row.hit_days = 1 if wins else 0
        row.sample = len(settled)
        row.pnl = round(pnl, 4)
        row.roi = round(pnl / len(settled), 6) if settled else None
        row.computed_at = utcnow()
        n += 1
    db.commit()
    return n
