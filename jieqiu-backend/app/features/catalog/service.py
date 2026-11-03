"""公开目录查询：比赛列表、判决流、真实成本、避雷/水位、日历、SP 异动、哨兵、实况。"""
from __future__ import annotations

import calendar as _calendar
from datetime import date as _date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import Event, MatchResult, SPMatch, SPSnapshot, Verdict
from ...modules.messaging import avoid_reason
from ...modules.timeutil import trade_date_from_kickoff

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))
STATUSES = ("promoted", "screening", "killed", "unjudged")


def parse_date(value: str) -> _date:
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("date 必须是 YYYY-MM-DD")
    if d.year > 2100:
        raise ValueError("date 超出支持范围")
    return d


def date_window(d: _date) -> tuple[str, str]:
    """竞彩日窗口：当日 05:00 至次日 04:59:59（00:00–04:59 属于前一日）。"""
    return f"{d.isoformat()} 05:00:00", f"{(d + timedelta(days=1)).isoformat()} 04:59:59"


def _latest_verdicts(db: Session, match_ids: list[str]) -> dict[str, Verdict]:
    if not match_ids:
        return {}
    latest: dict[str, Verdict] = {}
    for v in db.scalars(
            select(Verdict).where(Verdict.match_id.in_(match_ids))
            .order_by(Verdict.trade_date)):
        latest[v.match_id] = v
    return latest


def _gate_results(v: Verdict | None) -> dict[str, str] | None:
    if not v:
        return None
    return {k: (g.get("result", "") if isinstance(g, dict) else str(g))
            for k, g in v.gates.items()}


def _card(v: Verdict) -> dict:
    return {
        "id": v.id,
        "match_id": v.match_id,
        "match_no": v.match_no,
        "league": v.league,
        "home": v.home,
        "away": v.away,
        "kickoff": v.kickoff,
        "pool": v.pool,
        "goal_line": v.goal_line or "",
        "sp": {"h": v.sp_h, "d": v.sp_d, "a": v.sp_a},
        "rake": v.rake,
        "rake_threshold": v.rake_threshold,
        "probs": {"home": v.p_home, "draw": v.p_draw, "away": v.p_away},
        "pick": v.pick,
        "status": v.status,
        "gates": _gate_results(v) or {},
        "hash": v.payload_hash,
        "sealed": v.sealed_at is not None,
    }


def list_matches(db: Session, date: str, status: str | None = None,
                 league: str | None = None, limit: int = 100) -> dict:
    d = parse_date(date)
    start, end = date_window(d)
    rows = db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= start, SPMatch.kickoff <= end)
        .order_by(SPMatch.kickoff)).all()
    if league:
        rows = [m for m in rows if m.league == league]
    latest = _latest_verdicts(db, [m.match_id for m in rows])
    items = []
    for m in rows:
        v = latest.get(m.match_id)
        if status == "unjudged" and v is not None:
            continue
        if status and status != "unjudged" and (v is None or v.status != status):
            continue
        items.append({
            "match_id": m.match_id, "match_no": m.match_no, "league": m.league,
            "home": m.home, "away": m.away, "kickoff": m.kickoff,
            "sale_close": m.kickoff, "single": bool(m.single_flag),
            "verdict_id": v.id if v else None,
            "status": v.status if v else None,
            "rake": v.rake if v else None,
            "gates": _gate_results(v),
            "sp": {"h": v.sp_h, "d": v.sp_d, "a": v.sp_a} if v else None,
        })
    return {"date": d.isoformat(), "count": len(items), "matches": items[:limit]}


def verdicts_today(db: Session, date: str) -> dict:
    d = parse_date(date)
    rows = db.scalars(
        select(Verdict).where(Verdict.trade_date == d.isoformat())
        .order_by(Verdict.rake)).all()
    stats = {
        "total": len(rows),
        "promoted": sum(1 for v in rows if v.status == "promoted"),
        "screening": sum(1 for v in rows if v.status == "screening"),
        "killed": sum(1 for v in rows if v.status == "killed"),
    }
    return {"date": d.isoformat(), "stats": stats, "items": [_card(v) for v in rows]}


def true_cost(db: Session, match_id: str, pool: str | None = None) -> dict | None:
    m = db.get(SPMatch, match_id)
    if m is None:
        return None
    q = select(SPSnapshot).where(SPSnapshot.match_id == match_id)
    count_q = select(func.count(SPSnapshot.id)).where(SPSnapshot.match_id == match_id)
    if pool:
        q = q.where(SPSnapshot.pool == pool)
        count_q = count_q.where(SPSnapshot.pool == pool)
    snap = db.scalar(q.order_by(SPSnapshot.id.desc()).limit(1))
    if snap is None:
        return None
    snapshot_count = db.scalar(count_q) or 0
    if min(snap.sp_h, snap.sp_d, snap.sp_a) <= 1:
        raise ValueError("SP 数据异常：赔率必须大于 1")
    inv = {"h": 1.0 / snap.sp_h, "d": 1.0 / snap.sp_d, "a": 1.0 / snap.sp_a}
    total = sum(inv.values())
    fair = {k: v / total for k, v in inv.items()}
    sp = {"h": snap.sp_h, "d": snap.sp_d, "a": snap.sp_a}
    fair_odds = {k: 1.0 / fair[k] for k in fair}
    ev = {k: round(fair[k] * sp[k] - 1.0, 6) for k in fair}
    return {
        "match_id": m.match_id, "match_no": m.match_no, "home": m.home, "away": m.away,
        "pool": snap.pool, "goal_line": snap.goal_line or "",
        "sp": sp, "captured_at": snap.captured_at,
        "snapshot_count": snapshot_count,
        "implied_total": round(total, 6),
        "rake": round(total - 1.0, 6),
        "rake_pct": round((total - 1.0) * 100, 2),
        "fair_probs": {k: round(fair[k], 6) for k in fair},
        "fair_odds": {k: round(fair_odds[k], 4) for k in fair_odds},
        "ev_per_100": {k: round(ev[k] * 100, 2) for k in ev},
        "cost_per_100": round(-ev["h"] * 100, 2),
        "note": "真实成本 = 抽水已在赔率里。cost_per_100 是每 100 元按公平赔率应保留、实际被抽水拿走的部分；不构成投注建议。",
    }


def match_evidence(db: Session, match_id: str, date: str | None = None) -> dict | None:
    m = db.get(SPMatch, match_id)
    if m is None:
        return None
    q = select(Verdict).where(Verdict.match_id == match_id)
    if date:
        q = q.where(Verdict.trade_date == parse_date(date).isoformat())
    v = db.scalar(q.order_by(Verdict.trade_date.desc()).limit(1))
    if v is None:
        return None
    payload = v.payload or {}
    return {
        "match_id": m.match_id, "match_no": m.match_no, "league": m.league,
        "home": m.home, "away": m.away, "kickoff": m.kickoff,
        "verdict_id": v.id, "verdict_status": v.status,
        "evidence": payload.get("evidence", []),
        "data_cutoff": payload.get("data_cutoff"),
        "payload_hash": v.payload_hash,
        "sealed_at": v.sealed_at.isoformat() if v.sealed_at else None,
    }


def avoid_list(db: Session, date: str, limit: int = 50) -> dict:
    d = parse_date(date)
    rows = db.scalars(
        select(Verdict).where(Verdict.trade_date == d.isoformat(),
                              Verdict.status == "killed")
        .order_by(Verdict.rake.desc())).all()
    items = []
    for v in rows[:limit]:
        gate, why = avoid_reason(v)
        items.append({
            "verdict_id": v.id, "match_id": v.match_id, "match_no": v.match_no,
            "home": v.home, "away": v.away, "league": v.league,
            "kickoff": v.kickoff, "rake": v.rake, "gate": gate, "why": why,
        })
    return {"date": d.isoformat(), "count": len(items), "items": items}


def water_rank(db: Session, date: str, limit: int = 3) -> dict:
    d = parse_date(date)
    rows = db.scalars(
        select(Verdict).where(Verdict.trade_date == d.isoformat())
        .order_by(Verdict.rake.asc())).all()
    items = []
    for i, v in enumerate(rows[:limit], 1):
        items.append({
            "rank": i, "verdict_id": v.id, "match_id": v.match_id,
            "match_no": v.match_no, "home": v.home, "away": v.away,
            "league": v.league, "kickoff": v.kickoff, "rake": v.rake,
            "return_pct": round((1 - v.rake) * 100, 2),
            "status": v.status,
            "gates": _gate_results(v) or {},
        })
    return {"date": d.isoformat(), "count": len(items), "items": items}


def calendar_month(db: Session, month: str | None = None) -> dict:
    now_cn = datetime.now(CN)
    if month is None:
        month = now_cn.strftime("%Y-%m")
    try:
        year_s, month_s = month.split("-")
        year, mon = int(year_s), int(month_s)
        first = _date(year, mon, 1)
    except (TypeError, ValueError):
        raise ValueError("month 必须是 YYYY-MM")
    if not (2000 <= year <= 2100):
        raise ValueError("month 超出支持范围")
    last_day = _calendar.monthrange(year, mon)[1]
    last = _date(year, mon, last_day)
    next_first = last + timedelta(days=1)
    matches = db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= f"{first.isoformat()} 00:00:00",
        SPMatch.kickoff < f"{next_first.isoformat()} 00:00:00")).all()
    verdicts = db.scalars(select(Verdict).where(
        Verdict.trade_date >= first.isoformat(),
        Verdict.trade_date <= last.isoformat())).all()
    by_date: dict[str, dict[str, int]] = {}
    for i in range(last_day):
        key = (first + timedelta(days=i)).isoformat()
        by_date[key] = {"date": key, "matches": 0, "verdicts": 0,
                        "promoted": 0, "screening": 0, "killed": 0}
    for m in matches:
        key = trade_date_from_kickoff(m.kickoff)
        if key in by_date:
            by_date[key]["matches"] += 1
    for v in verdicts:
        key = v.trade_date
        if key in by_date:
            by_date[key]["verdicts"] += 1
            if v.status in ("promoted", "screening", "killed"):
                by_date[key][v.status] += 1
    days = list(by_date.values())
    return {"month": f"{year:04d}-{mon:02d}", "total_matches": len(matches), "days": days}


def sp_movements(db: Session, date: str | None = None, limit: int = 50) -> dict:
    d = parse_date(date) if date else datetime.now(CN).date()
    rows = db.scalars(
        select(SPSnapshot).where(
            SPSnapshot.captured_at >= d.isoformat(),
            SPSnapshot.captured_at < (d + timedelta(days=1)).isoformat())
        .order_by(SPSnapshot.captured_at.desc(), SPSnapshot.id.desc())
        .limit(5000)).all()
    grouped: dict[tuple[str, str], list[SPSnapshot]] = {}
    for s in rows:
        key = (s.match_id, s.pool)
        bucket = grouped.setdefault(key, [])
        if len(bucket) < 2:
            bucket.append(s)
    ids = list({mid for mid, _pool in grouped})
    matches = {m.match_id: m for m in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(ids)))} if ids else {}
    items = []
    for (match_id, pool), snaps in grouped.items():
        latest = snaps[0]
        prev = snaps[1] if len(snaps) > 1 else None
        m = matches.get(match_id)
        delta = None
        delta_pct = None
        if prev is not None:
            delta = {k: round(getattr(latest, f"sp_{k}") - getattr(prev, f"sp_{k}"), 3)
                     for k in ("h", "d", "a")}
            delta_pct = {k: (round((getattr(latest, f"sp_{k}") / getattr(prev, f"sp_{k}") - 1) * 100, 2)
                             if getattr(prev, f"sp_{k}") else None)
                         for k in ("h", "d", "a")}
        items.append({
            "match_id": match_id,
            "match_no": m.match_no if m else "",
            "home": m.home if m else "",
            "away": m.away if m else "",
            "pool": pool, "goal_line": latest.goal_line or "",
            "captured_at": latest.captured_at,
            "prev_captured_at": prev.captured_at if prev else None,
            "sp": {"h": latest.sp_h, "d": latest.sp_d, "a": latest.sp_a},
            "prev_sp": ({"h": prev.sp_h, "d": prev.sp_d, "a": prev.sp_a}
                        if prev else None),
            "delta": delta, "delta_pct": delta_pct,
        })
    items.sort(key=lambda x: (abs(sum((x["delta"] or {}).values())), x["captured_at"]),
               reverse=True)
    items = items[:limit]
    return {"date": d.isoformat(), "count": len(items), "items": items}


def sentinel_feed(db: Session, match_id: str | None = None, limit: int = 50) -> dict:
    q = select(Event)
    if match_id:
        q = q.where(Event.match_id == match_id)
    rows = db.scalars(q.order_by(Event.id.desc()).limit(limit)).all()
    ids = {e.match_id for e in rows if e.match_id}
    matches = {m.match_id: m for m in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(ids)))} if ids else {}
    items = []
    for e in rows:
        m = matches.get(e.match_id or "")
        items.append({
            "id": e.id, "type": e.type, "severity": e.severity,
            "match_id": e.match_id, "match_no": m.match_no if m else None,
            "home": m.home if m else None, "away": m.away if m else None,
            "payload": e.payload or {}, "data_cutoff": e.data_cutoff,
            "created_at": e.created_at.isoformat(),
            "fanned_out": e.fanout_at is not None,
        })
    return {"count": len(items), "items": items}


def match_live(db: Session, match_id: str) -> dict | None:
    m = db.get(SPMatch, match_id)
    if m is None:
        return None
    kickoff = datetime.strptime(m.kickoff[:19], "%Y-%m-%d %H:%M:%S")
    now_cn = datetime.now(CN).replace(tzinfo=None)
    d = kickoff.date()
    result = db.scalar(
        select(MatchResult).where(
            MatchResult.home == m.home, MatchResult.away == m.away,
            MatchResult.match_date >= (d - timedelta(days=1)).isoformat(),
            MatchResult.match_date <= (d + timedelta(days=1)).isoformat())
        .order_by(MatchResult.id.desc()).limit(1))
    snaps = db.scalars(
        select(SPSnapshot).where(SPSnapshot.match_id == match_id)
        .order_by(SPSnapshot.id.desc()).limit(20)).all()
    timeline = [{
        "captured_at": s.captured_at, "pool": s.pool,
        "goal_line": s.goal_line or "",
        "sp": {"h": s.sp_h, "d": s.sp_d, "a": s.sp_a},
    } for s in reversed(snaps)]
    if result is not None:
        state = "finished"
        score = f"{result.goals_home}-{result.goals_away}"
    elif now_cn < kickoff:
        state, score = "scheduled", None
    else:
        state, score = "awaiting_result", None
    return {
        "match_id": m.match_id, "match_no": m.match_no, "league": m.league,
        "home": m.home, "away": m.away, "kickoff": m.kickoff,
        "state": state, "live_feed": False, "score": score,
        "result_source": result.source if result else None,
        "updated_at": (result.retrieved_at if result else
                       (snaps[0].captured_at if snaps else None)),
        "timeline": timeline,
        "note": ("实时事件源尚未接入：这里只展示已同步赛果与 SP 快照，"
                 "不生成虚构的进球时间线。终场结果由赛果同步任务回填。"),
    }
