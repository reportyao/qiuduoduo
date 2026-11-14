"""4 场定投计划：选场、组合、结算、收益读模型。

v1 只处理 1X2/让球；每条腿 allocation=100。
串关不是额外加钱：两场的 100 合并成 200 的 2 串 1。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (DecisionSnapshot, MarketSettlement, PlanBet, PlanBetLeg,
                      PlanCycle, Verdict, utcnow)
from .timeutil import CN, trade_date_now

RISK_LABEL = {"stable": "稳健定投", "balanced": "平衡定投", "aggressive": "进取定投"}
RISK_ORDER = ("stable", "balanced", "aggressive")
_DIRS = ("home", "draw", "away")
DIR_LABEL = {"home": "主胜", "draw": "平局", "away": "客胜"}


def _dir(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    return {"主胜": "home", "主": "home", "home": "home",
            "平局": "draw", "平": "draw", "draw": "draw",
            "客胜": "away", "客": "away", "away": "away"}.get(v)


def _odds(v: Verdict, d: str) -> float | None:
    try:
        pick_sp = (v.pick or {}).get("sp")
        if pick_sp and float(pick_sp) > 1:
            return float(pick_sp)
        return float({"home": v.sp_h, "draw": v.sp_d, "away": v.sp_a}[d])
    except (TypeError, ValueError, KeyError):
        return None


def _model_prob(v: Verdict, d: str) -> float | None:
    try:
        raw = {"home": v.model_h, "draw": v.model_d, "away": v.model_a}[d]
        if raw is not None and 0 < float(raw) <= 1:
            return float(raw)
        p = (v.pick or {}).get("prob")
        return float(p) if p is not None and 0 < float(p) <= 1 else None
    except (TypeError, ValueError, KeyError):
        return None


def _market_prob(v: Verdict, d: str) -> float | None:
    try:
        return float({"home": v.p_home, "draw": v.p_draw, "away": v.p_away}[d])
    except (TypeError, ValueError, KeyError):
        return None


def _candidates(db: Session, date: str) -> list[dict]:
    """优先读已发布 snapshot；没有则用 promoted 作为内部生成候选。"""
    rows = db.execute(
        select(DecisionSnapshot, Verdict)
        .join(Verdict, DecisionSnapshot.verdict_id == Verdict.id)
        .where(DecisionSnapshot.trade_date == date,
               DecisionSnapshot.status == "published")
    ).all()
    seen: set[str] = set()
    out: list[dict] = []
    now_cn = datetime.now(CN).strftime("%Y-%m-%d %H:%M:%S")
    now_utc = utcnow()
    for snap, v in rows:
        if v.id in seen or v.settled is not None:
            continue
        if v.kickoff <= now_cn:
            continue
        if snap.expires_at is not None and snap.expires_at <= now_utc:
            continue
        seen.add(v.id)
        item = _score(v)
        if item:
            out.append(item)
    if out:
        return out
    # 兼容没有发布快照的早期环境；只使用 promoted + verified。
    for v in db.scalars(select(Verdict).where(Verdict.trade_date == date)).all():
        if v.status != "promoted" or not v.pick or v.settled is not None:
            continue
        if v.kickoff <= now_cn:
            continue
        if v.tier not in ("verified", ""):
            continue
        item = _score(v)
        if item:
            out.append(item)
    return out


def _score(v: Verdict) -> dict | None:
    d = _dir((v.pick or {}).get("dir"))
    if d is None:
        return None
    odds = _odds(v, d)
    mp = _market_prob(v, d)
    model = _model_prob(v, d)
    if not odds or odds <= 1 or mp is None or model is None:
        return None
    edge = model - mp
    ev = model * odds - 1
    gates = {k: (g or {}).get("result") for k, g in (v.gates or {}).items()}
    quality = 1.0 if all(gates.get(k) == "pass" for k in ("price", "market", "model")) else 0.5
    # 低赔率不是加分项；edge/EV/quality 才是。
    score = edge * 100 + ev * 10 + quality
    if edge <= 0 or ev <= 0:
        return None
    return {
        "verdict": v, "dir": d, "odds": odds, "market_prob": mp,
        "model_prob": model, "edge": edge, "ev": ev,
        "quality": quality, "score": round(score, 4),
        "reason": f"edge {edge*100:+.1f}pp · EV {ev*100:+.1f}% · 数据质量 {'高' if quality >= 1 else '中'}",
    }


def _pick_diverse(cands: list[dict], limit: int = 4) -> list[dict]:
    out: list[dict] = []
    league_count: dict[str, int] = {}
    seen_matches: set[str] = set()
    for c in sorted(cands, key=lambda x: x["score"], reverse=True):
        v = c["verdict"]
        if v.match_id in seen_matches:
            continue
        if league_count.get(v.league, 0) >= 2:
            continue
        seen_matches.add(v.match_id)
        league_count[v.league] = league_count.get(v.league, 0) + 1
        out.append(c)
        if len(out) >= limit:
            break
    return out


def _bet(db: Session, cycle: PlanCycle, picks: list[dict],
         bet_type: str, label: str) -> PlanBet:
    stake = sum(100.0 for _ in picks)
    odds = 1.0
    for p in picks:
        odds *= p["odds"]
    bet = PlanBet(
        id=uuid.uuid4().hex, cycle_id=cycle.id, bet_type=bet_type,
        label=label, stake=round(stake, 2), odds=round(odds, 4),
        status="pending",
    )
    db.add(bet)
    db.flush()
    for p in picks:
        v = p["verdict"]
        db.add(PlanBetLeg(
            bet_id=bet.id, verdict_id=v.id, match_id=v.match_id,
            market="hhad" if v.pool == "hhad" else "had",
            line=v.goal_line if v.pool == "hhad" else "",
            direction=DIR_LABEL.get(p["dir"], p["dir"]), odds=round(p["odds"], 4),
            allocation=100.0, model_prob=round(p["model_prob"], 6),
            market_prob=round(p["market_prob"], 6),
            edge=round(p["edge"], 6), quality_score=round(p["quality"], 4),
            selection_reason=p["reason"][:240],
        ))
    return bet


def build_cycle(db: Session, risk: str = "stable", date: str | None = None,
                publish: bool = True) -> PlanCycle | None:
    if risk not in RISK_ORDER:
        raise ValueError("risk 必须是 stable/balanced/aggressive")
    date = date or trade_date_now()
    cands = _pick_diverse(_candidates(db, date), 4)
    if not cands:
        return None
    last_no = db.scalar(select(PlanCycle.cycle_no).where(
        PlanCycle.risk_level == risk).order_by(PlanCycle.cycle_no.desc()).limit(1)) or 0
    cycle = PlanCycle(
        id=uuid.uuid4().hex, name=RISK_LABEL[risk], risk_level=risk,
        cycle_no=int(last_no) + 1, start_at=f"{date} 05:00:00",
        end_at=max(c["verdict"].kickoff for c in cands),
        budget=400.0, target_matches=4,
        status="published" if publish else "draft",
        selection_version="v1",
        model_version=str((cands[0]["verdict"].payload or {}).get("model", {}).get("engine") or "dc"),
        published_at=utcnow() if publish else None,
    )
    db.add(cycle)
    db.flush()
    if risk == "stable":
        for c in cands:
            _bet(db, cycle, [c], "single", "单关")
    elif risk == "balanced" and len(cands) >= 2:
        _bet(db, cycle, cands[:2], "parlay", "2 串 1")
        for c in cands[2:4]:
            _bet(db, cycle, [c], "single", "单关")
    elif risk == "aggressive" and len(cands) >= 4:
        _bet(db, cycle, cands[:2], "parlay", "2 串 1")
        _bet(db, cycle, cands[2:4], "parlay", "2 串 1")
    elif len(cands) >= 2:
        _bet(db, cycle, cands[:2], "parlay", "2 串 1")
        for c in cands[2:4]:
            _bet(db, cycle, [c], "single", "单关")
    else:
        _bet(db, cycle, [cands[0]], "single", "单关")
    _recalc_cycle(db, cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def ensure_today_cycles(db: Session, date: str | None = None) -> list[PlanCycle]:
    """seed 用：每个 risk 当天没有已发布期数才生成，避免每 30 分钟重复建期。"""
    date = date or trade_date_now()
    out: list[PlanCycle] = []
    for risk in RISK_ORDER:
        exists = db.scalar(select(PlanCycle).where(
            PlanCycle.risk_level == risk,
            PlanCycle.start_at.like(f"{date}%"),
            PlanCycle.status.in_(("published", "settled")),
        ).limit(1))
        if exists is not None:
            continue
        cycle = build_cycle(db, risk, date=date, publish=True)
        if cycle is not None:
            out.append(cycle)
    return out


def _recalc_cycle(db: Session, cycle: PlanCycle) -> None:
    bets = list(db.scalars(select(PlanBet).where(
        PlanBet.cycle_id == cycle.id).order_by(PlanBet.created_at)).all())
    cycle.total_stake = round(sum(b.stake for b in bets), 2)
    settled_bets = [b for b in bets if b.status in ("won", "lost", "void")]
    cycle.total_return = round(sum(b.pnl + b.stake for b in settled_bets), 2)
    cycle.pnl = round(sum(b.pnl for b in settled_bets), 2)
    cycle.roi = round(cycle.pnl / cycle.total_stake, 6) if cycle.total_stake else None
    running = peak = max_dd = 0.0
    for bet in settled_bets:
        running += bet.pnl
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
    cycle.max_drawdown = round(-max_dd, 2)
    if bets and all(b.status in ("won", "lost", "void") for b in bets):
        cycle.status = "settled"
    cycle.updated_at = utcnow()


def settle_cycle(db: Session, cycle: PlanCycle) -> bool:
    """结算计划：先结算 verdict，再按串关规则更新 plan_bet。"""
    from .settlement import settle_pending
    settle_pending(db)
    bets = list(db.scalars(select(PlanBet).where(PlanBet.cycle_id == cycle.id)).all())
    changed = False
    for bet in bets:
        legs = list(db.scalars(select(PlanBetLeg).where(PlanBetLeg.bet_id == bet.id)).all())
        if not legs:
            continue
        statuses = []
        for leg in legs:
            v = db.get(Verdict, leg.verdict_id)
            if v is None or v.settled not in ("win", "lose", "void"):
                statuses.append("pending")
            else:
                leg.result = v.settled
                leg.settled_at = v.settled_at
                statuses.append(v.settled)
                row = db.scalar(select(MarketSettlement).where(
                    MarketSettlement.subject_type == "plan_bet",
                    MarketSettlement.subject_id == bet.id,
                    MarketSettlement.leg_index == legs.index(leg),
                    MarketSettlement.market == leg.market,
                    MarketSettlement.line == leg.line,
                    MarketSettlement.direction == leg.direction,
                    MarketSettlement.rules_version == "v1",
                ))
                if row is None:
                    row = MarketSettlement(
                        subject_type="plan_bet", subject_id=bet.id,
                        leg_index=legs.index(leg), market=leg.market,
                        line=leg.line, direction=leg.direction,
                        rules_version="v1",
                    )
                    db.add(row)
                row.result = v.settled
                row.won = None if v.settled == "void" else v.settled == "win"
                row.source = "plan_cycle"
                row.settled_at = v.settled_at
        if any(s == "pending" for s in statuses):
            continue
        if any(s == "lose" for s in statuses):
            bet.status, bet.pnl = "lost", -bet.stake
        elif all(s == "win" for s in statuses):
            bet.status, bet.pnl = "won", round((bet.odds - 1) * bet.stake, 2)
        else:
            # 有走水/取消腿且没有输腿：整注按走水处理，退回本金。
            bet.status, bet.pnl = "void", 0.0
        bet.settled_at = utcnow()
        changed = True
    _recalc_cycle(db, cycle)
    db.commit()
    return changed


def settle_open_cycles(db: Session) -> int:
    """结算所有已发布但未完成的计划；由赛果同步/seed/后台调用。

    OPC：与 settle_pending 同模式——job 失败记 ops_jobs + ops_exception 后
    吞掉异常返回 0，不让调度链（seed/cron）被单次结算失败拖死。
    """
    from . import ops
    job_id = ops.job_start(db, "settle_open_cycles")
    try:
        cycles = list(db.scalars(select(PlanCycle).where(
            PlanCycle.status == "published")).all())
        n = 0
        for cycle in cycles:
            if settle_cycle(db, cycle):
                n += 1
        ops.job_finish(db, job_id, "ok")
        return n
    except Exception as exc:
        db.rollback()
        ops.job_finish(db, job_id, "error", f"{type(exc).__name__}: {exc}")
        ops.exception(db, "settle_open_cycles_error", str(exc), severity=3,
                      source="settle_open_cycles", dedupe_key="settle_open_cycles_error")
        return 0


def _leg_payload(db: Session, leg: PlanBetLeg) -> dict:
    verdict = db.get(Verdict, leg.verdict_id)
    return {
        "verdict_id": leg.verdict_id, "match_id": leg.match_id,
        "match_no": verdict.match_no if verdict else "",
        "league": verdict.league if verdict else "",
        "home": verdict.home if verdict else "",
        "away": verdict.away if verdict else "",
        "market": leg.market, "line": leg.line,
        "direction": leg.direction, "odds": leg.odds,
        "allocation": leg.allocation, "model_prob": leg.model_prob,
        "market_prob": leg.market_prob, "edge": leg.edge,
        "quality_score": leg.quality_score,
        "selection_reason": leg.selection_reason,
        "result": leg.result,
    }


def cycle_detail(db: Session, cycle: PlanCycle, include_legs: bool) -> dict:
    bets = list(db.scalars(select(PlanBet).where(
        PlanBet.cycle_id == cycle.id).order_by(PlanBet.created_at)).all())
    data = {
        "id": cycle.id, "name": cycle.name, "risk_level": cycle.risk_level,
        "cycle_no": cycle.cycle_no, "start_at": cycle.start_at,
        "end_at": cycle.end_at, "budget": cycle.budget,
        "target_matches": cycle.target_matches, "status": cycle.status,
        "total_stake": cycle.total_stake, "total_return": cycle.total_return,
        "pnl": cycle.pnl, "roi": cycle.roi,
        "max_drawdown": cycle.max_drawdown,
        "published_at": cycle.published_at.isoformat() if cycle.published_at else None,
        "bet_count": len(bets), "match_count": len({l.match_id for b in bets for l in db.scalars(
            select(PlanBetLeg).where(PlanBetLeg.bet_id == b.id)).all()}),
        "bets": [],
    }
    if include_legs:
        for b in bets:
            legs = list(db.scalars(select(PlanBetLeg).where(
                PlanBetLeg.bet_id == b.id).order_by(PlanBetLeg.id)).all())
            data["bets"].append({
                "id": b.id, "bet_type": b.bet_type, "label": b.label,
                "stake": b.stake, "odds": b.odds, "status": b.status,
                "pnl": b.pnl, "legs": [_leg_payload(db, l) for l in legs],
            })
    return data


def current(db: Session, risk: str, include_legs: bool) -> dict | None:
    cycle = db.scalar(select(PlanCycle).where(
        PlanCycle.risk_level == risk,
        PlanCycle.status.in_(("published", "settled")),
    ).order_by(PlanCycle.cycle_no.desc()).limit(1))
    return cycle_detail(db, cycle, include_legs) if cycle else None


def history(db: Session, risk: str, limit: int = 30, include_legs: bool = False) -> list[dict]:
    rows = db.scalars(select(PlanCycle).where(
        PlanCycle.risk_level == risk,
        PlanCycle.status.in_(("published", "settled")),
    ).order_by(PlanCycle.cycle_no.desc()).limit(max(1, min(limit, 100)))).all()
    return [cycle_detail(db, c, include_legs) for c in rows]


def summary(db: Session) -> dict:
    out = {}
    for risk in RISK_ORDER:
        rows = db.scalars(select(PlanCycle).where(
            PlanCycle.risk_level == risk,
            PlanCycle.status.in_(("published", "settled")),
        ).order_by(PlanCycle.cycle_no)).all()
        settled = [c for c in rows if c.status == "settled"]
        out[risk] = {
            "name": RISK_LABEL[risk],
            "cycles": len(rows),
            "settled": len(settled),
            "pnl": round(sum(c.pnl for c in settled), 2),
            "roi": round(sum(c.pnl for c in settled) / max(1.0, sum(c.total_stake for c in settled)), 6),
            "last_7d": round(sum(c.pnl for c in settled if c.start_at >= (
                datetime.now(CN) - timedelta(days=7)).strftime("%Y-%m-%d")), 2),
            "last_30d": round(sum(c.pnl for c in settled if c.start_at >= (
                datetime.now(CN) - timedelta(days=30)).strftime("%Y-%m-%d")), 2),
        }
    return out
