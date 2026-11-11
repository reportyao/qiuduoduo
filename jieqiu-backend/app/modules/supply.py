"""内容供给诊断：回答“为什么今天没有可发布的判断”。

推荐主链的前置条件是市闸至少有两个去水口径（竞彩官方 + 至少一条市场源）。
市场源优先使用 Sportmonks Pinnacle，The Odds API 作为兜底；两者都未覆盖时，
判决会停在 pending_data，不会 promoted，也不会有 published 内容。这个模块把
这条链路的每一环计数暴露给后台/健康检查，避免“首页空”却没人知道卡在哪。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (DecisionSnapshot, IntlOdds, RecommendationPlan, SPMatch,
                      SPSnapshot, SportmonksMatchData, Verdict)
from .sportmonks import market_is_fresh
from .timeutil import CN, trade_date_now, trade_window


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return int(db.scalar(stmt) or 0)


def content_supply(db: Session, date: str | None = None) -> dict:
    """当日内容供给漏斗：场次 → SP → 判决 → 市闸 → promoted → published。"""
    date = date or trade_date_now()
    start, end = trade_window(date)
    matches = list(db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= start, SPMatch.kickoff <= end)
        .order_by(SPMatch.kickoff)).all())
    match_ids = [m.match_id for m in matches]
    sp_snapshots = (
        _count(db, SPSnapshot, SPSnapshot.match_id.in_(match_ids))
        if match_ids else 0)

    verdicts = list(db.scalars(
        select(Verdict).where(Verdict.trade_date == date)).all())
    status_counts = {"total": len(verdicts), "promoted": 0, "screening": 0,
                     "killed": 0}
    market = {"pass": 0, "fail": 0, "pending_data": 0, "missing": 0}
    for v in verdicts:
        if v.status in status_counts:
            status_counts[v.status] += 1
        gate = (v.gates or {}).get("market") or {}
        result = gate.get("result") if isinstance(gate, dict) else gate
        if result in market:
            market[result] += 1
        else:
            market["missing"] += 1

    now = datetime.now(CN).replace(tzinfo=None)
    not_expired_snap = or_(DecisionSnapshot.expires_at.is_(None),
                           DecisionSnapshot.expires_at > now)
    not_expired_plan = or_(RecommendationPlan.expires_at.is_(None),
                           RecommendationPlan.expires_at > now)
    published_snaps = _count(
        db, DecisionSnapshot, DecisionSnapshot.trade_date == date,
        DecisionSnapshot.status == "published", not_expired_snap)
    published_plans = _count(
        db, RecommendationPlan, RecommendationPlan.trade_date == date,
        RecommendationPlan.status == "published", not_expired_plan)
    snapshots_total = _count(
        db, DecisionSnapshot, DecisionSnapshot.trade_date == date)
    plans_total = _count(
        db, RecommendationPlan, RecommendationPlan.trade_date == date)

    intl_total = _count(db, IntlOdds)
    intl_latest = db.scalar(
        select(IntlOdds.retrieved_at).order_by(IntlOdds.retrieved_at.desc()).limit(1))
    # 一次批量取国际盘窗口，避免逐场 N+1 查询（后台数据页会定时刷新）。
    by_pair: dict[tuple[str, str], list[IntlOdds]] = {}
    if matches:
        lo = (datetime.strptime(start, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
              - timedelta(hours=4)).astimezone(timezone.utc).isoformat()
        hi = (datetime.strptime(end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
              + timedelta(hours=4)).astimezone(timezone.utc).isoformat()
        homes = {m.home for m in matches}
        aways = {m.away for m in matches}
        rows = db.scalars(select(IntlOdds).where(
            IntlOdds.kickoff_utc >= lo, IntlOdds.kickoff_utc <= hi,
            IntlOdds.home.in_(homes), IntlOdds.away.in_(aways))).all()
        for row in rows:
            by_pair.setdefault((row.home, row.away), []).append(row)
    sm_rows = {r.match_id: r for r in db.scalars(
        select(SportmonksMatchData).where(
            SportmonksMatchData.match_id.in_([m.match_id for m in matches]))
    ).all()} if matches else {}
    per_match = []
    for m in matches:
        sources = []
        for row in by_pair.get((m.home, m.away), []):
            if row.source not in sources:
                sources.append(row.source)
        sm = sm_rows.get(m.match_id)
        sm_market = market_is_fresh(sm)
        per_match.append({
            "match_id": m.match_id,
            "match_no": m.match_no,
            "home": m.home,
            "away": m.away,
            "kickoff": m.kickoff,
            "intl_sources": sources,
            "intl_covered": bool(sources),
            "sm_market": sm_market,
            "sm_bookmaker": sm.bookmaker if sm else "",
            "market_covered": bool(sources) or sm_market,
        })
    sm_market_covered = sum(1 for row in per_match if row["sm_market"])

    odds_configured = bool(get_settings().odds_api_key)
    blocked_reason = None
    if not matches:
        blocked_reason = "今日无在售场次"
    elif not verdicts:
        blocked_reason = "采集/判决未生成"
    elif intl_total == 0 and sm_market_covered == 0:
        blocked_reason = "Sportmonks Pinnacle 与国际盘均未接入，市闸无法通过"
    elif market["pending_data"] >= len(verdicts):
        blocked_reason = "市闸全部 pending（市场覆盖不足）"
    elif published_snaps + published_plans == 0:
        blocked_reason = "暂无已发布判断"
    return {
        "date": date,
        "matches": len(matches),
        "sp_snapshots": sp_snapshots,
        "verdicts": status_counts,
        "market_gate": market,
        "snapshots": {"total": snapshots_total, "published": published_snaps},
        "plans": {"total": plans_total, "published": published_plans},
        "published": published_snaps + published_plans,
        "intl_odds": {
            "total": intl_total,
            "latest": intl_latest,
            "configured": odds_configured,
            "covered_matches": sum(1 for m in per_match if m["intl_covered"]),
            "missing_matches": sum(1 for m in per_match if not m["intl_covered"]),
        },
        "sportmonks_market": {
            "covered_matches": sm_market_covered,
            "missing_matches": sum(1 for m in per_match if not m["sm_market"]),
        },
        "market_covered_matches": sum(1 for m in per_match if m["market_covered"]),
        "per_match": per_match,
        "blocked_reason": blocked_reason,
    }
