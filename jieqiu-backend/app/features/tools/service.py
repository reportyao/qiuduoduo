"""串关体检：成本 / 信息 / 模型 / 结构四维分析。

只做确定性计算与事实聚合：
- 成本：单腿抽水、组合返还率、期望损耗
- 信息：focus.coverage / facts / unknowns
- 模型：verdict.model_* vs verdict.p_*（去水市场概率）
- 结构：腿数、同联赛/同时段、pending、停售状态

不输出“买/不买”建议；optimizations 只优化结构、信息和成本。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Verdict
from ...modules.timeutil import CN, trade_date_now, trade_window
from ..intel import service as intel_service
from ..intel.schemas import Coverage, IntelFact
from .schemas import (ParlayCheckRequest, ParlayCheckResponse, ParlayCombo,
                      ParlayLegOut, ParlayNote, ParlayPlanItem, ParlayPlanRequest,
                      ParlayPlanResponse, ParlayScores)

DIR_LABEL = {"home": "主胜", "draw": "平", "away": "客胜"}
_DIR_ATTR = {"home": ("sp_h", "p_home", "model_h"),
             "draw": ("sp_d", "p_draw", "model_d"),
             "away": ("sp_a", "p_away", "model_a")}
_COST_LOW = 0.12
_COST_MEDIUM = 0.24


def _f(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_kickoff(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
    except (TypeError, ValueError):
        return None


def _cost_level(cost_pct: float) -> str:
    if cost_pct <= _COST_LOW:
        return "low"
    if cost_pct <= _COST_MEDIUM:
        return "medium"
    return "high"


def _info_level(levels: list[str]) -> str:
    if levels and all(level == "full" for level in levels):
        return "good"
    if any(level == "insufficient" for level in levels):
        return "weak"
    return "partial"


def _model_level(covered: int, total: int) -> str:
    if total and covered == total:
        return "good"
    return "partial" if covered else "missing"


def _structure_risk(legs: list[ParlayLegOut], same_league: bool,
                    same_window: bool, pending: int) -> tuple[str, list[ParlayNote]]:
    risks: list[ParlayNote] = []
    level = "low"
    if len(legs) >= 4:
        level = "high"
        risks.append(ParlayNote(key="leg_count", level="high",
                                message=f"{len(legs)} 腿组合方差高，抽水叠加明显。"))
    elif len(legs) == 3:
        level = "medium"
        risks.append(ParlayNote(key="leg_count", level="medium",
                                message="3 腿组合比 2 腿更容易被单场意外拖垮。"))
    if pending:
        pending_level = "high" if pending >= 2 else "medium"
        if pending_level == "high":
            level = "high"
        elif level == "low":
            level = "medium"
        risks.append(ParlayNote(
            key="pending", level=pending_level,
            message=f"{pending} 腿仍在复核，组合结论只代表当前数据。"))
    if same_league and same_window:
        level = "high"
        risks.append(ParlayNote(
            key="correlation", level="high",
            message="同联赛且同时段，独立假设会高估组合概率。"))
    elif same_league:
        if level == "low":
            level = "medium"
        risks.append(ParlayNote(
            key="correlation", level="medium",
            message="同联赛存在相关性，独立假设可能偏乐观。"))
    return level, risks


def _optimizations(legs: list[ParlayLegOut], cost: float) -> list[ParlayNote]:
    out: list[ParlayNote] = []
    if len(legs) >= 3:
        out.append(ParlayNote(
            key="leg_count", level="medium",
            message="腿数越多，抽水叠加越明显；可对比单关成本后再决定结构。"))
    for idx, leg in enumerate(legs, start=1):
        if leg.model_prob is None:
            out.append(ParlayNote(
                key=f"model_{idx}", level="medium",
                message=f"第 {idx} 腿模型未覆盖：换一场有模型的腿，或等模型更新后再体检。"))
        if "lineups" in leg.coverage.missing:
            out.append(ParlayNote(
                key=f"lineups_{idx}", level="medium",
                message=f"第 {idx} 腿首发未公布：等首发确认再体检。"))
        if "price" in leg.coverage.missing:
            out.append(ParlayNote(
                key=f"price_{idx}", level="medium",
                message=f"第 {idx} 腿价格快照已过期：刷新后再体检。"))
        if "market" in leg.coverage.missing:
            out.append(ParlayNote(
                key=f"market_{idx}", level="low",
                message=f"第 {idx} 腿国际盘未覆盖：市闸无法判断。"))
        if leg.status != "promoted":
            out.append(ParlayNote(
                key=f"status_{idx}", level="medium",
                message=f"第 {idx} 腿状态为 {leg.status}，组合结论仅代表当前数据。"))
    if cost > 0:
        out.append(ParlayNote(
            key="cost", level="low",
            message=f"这组组合的抽水成本约 {cost:.2f} 元；可展开每腿看成本来源。"))
    return out[:10]


def check_parlay(db: Session, body: ParlayCheckRequest) -> ParlayCheckResponse:
    ids = [leg.verdict_id for leg in body.legs]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "同一场比赛不能重复选择")

    verdicts: dict[str, Verdict] = {}
    for vid in ids:
        v = db.get(Verdict, vid)
        if v is None:
            raise HTTPException(404, f"verdict not found: {vid}")
        verdicts[vid] = v
    match_ids = [v.match_id for v in verdicts.values()]
    if len(set(match_ids)) != len(match_ids):
        raise HTTPException(422, "同一场比赛不能重复选择")

    legs: list[ParlayLegOut] = []
    same_league = False
    same_window = False
    leagues = [v.league for v in verdicts.values() if v.league]
    if len(leagues) != len(set(leagues)):
        same_league = True
    kicks = [k for k in (_parse_kickoff(v.kickoff) for v in verdicts.values()) if k]
    for i, a in enumerate(kicks):
        for b in kicks[i + 1:]:
            if abs((a - b).total_seconds()) <= 90 * 60:
                same_window = True

    for item in body.legs:
        v = verdicts[item.verdict_id]
        sp_attr, market_attr, model_attr = _DIR_ATTR[item.dir]
        odds = _f(getattr(v, sp_attr))
        market_prob = _f(getattr(v, market_attr))
        model_prob = _f(getattr(v, model_attr))
        rake = _f(v.rake)
        if not odds or odds <= 1:
            raise HTTPException(422, f"{v.id} 缺少有效赔率")
        if market_prob is None or market_prob <= 0:
            raise HTTPException(422, f"{v.id} 缺少市场概率")
        if rake is None or not 0 <= rake < 1:
            raise HTTPException(422, f"{v.id} 缺少有效抽水")
        if model_prob is not None and not 0 < model_prob <= 1:
            model_prob = None
        focus = intel_service.build_focus(db, v.match_id, date=v.trade_date)
        if focus is None:
            raise HTTPException(422, f"{v.id} 缺少比赛数据")
        model_engine = ((v.payload or {}).get("model") or {}).get("engine")
        facts = [IntelFact(**f) for f in focus["intel"]["facts"]]
        legs.append(ParlayLegOut(
            verdict_id=v.id, match_id=v.match_id, match_no=v.match_no,
            league=v.league, home=v.home, away=v.away, kickoff=v.kickoff,
            dir=item.dir, dir_label=DIR_LABEL[item.dir], odds=odds,
            market_prob=round(market_prob, 4),
            model_prob=round(model_prob, 4) if model_prob is not None else None,
            model_edge=(round(model_prob - market_prob, 4)
                        if model_prob is not None else None),
            model_expected_return=(round(model_prob * odds, 4)
                                   if model_prob is not None else None),
            model_engine=model_engine, rake=round(rake, 4),
            status=v.status, gates={k: g.get("result", "unknown")
                                    for k, g in (v.gates or {}).items()},
            coverage=Coverage(**focus["coverage"]),
            facts=facts, unknowns=focus["intel"]["unknowns"],
            sealed=v.sealed_at is not None, payload_hash=v.payload_hash,
        ))

    combo_odds = 1.0
    market_return = 1.0
    model_return = 1.0
    model_prob_combo = 1.0
    model_covered = 0
    pending = 0
    for leg in legs:
        combo_odds *= leg.odds
        market_return *= (1 - leg.rake)
        if leg.model_prob is None:
            model_return = 0.0
        else:
            model_covered += 1
            model_return *= leg.model_prob * leg.odds
            model_prob_combo *= leg.model_prob
        if leg.status != "promoted":
            pending += 1
    if model_covered != len(legs):
        model_prob_combo = 0.0

    stake = float(body.stake)
    cost = stake - stake * market_return
    cost_pct = 1 - market_return
    combo_market_prob = 1 / combo_odds if combo_odds else 0.0
    combo = ParlayCombo(
        leg_count=len(legs), odds=round(combo_odds, 4),
        market_prob=round(combo_market_prob, 4),
        model_prob=round(model_prob_combo, 4) if model_covered == len(legs) else None,
        model_edge=(round(model_prob_combo - combo_market_prob, 4)
                    if model_covered == len(legs) else None),
        market_return_rate=round(market_return, 4),
        model_expected_return=(round(stake * model_return, 2)
                               if model_covered == len(legs) else None),
        market_expected_return=round(stake * market_return, 2),
        cost=round(cost, 2), cost_pct=round(cost_pct, 4),
        model_coverage=f"{model_covered}/{len(legs)}",
    )

    coverage_levels = [leg.coverage.level for leg in legs]
    structure, risks = _structure_risk(legs, same_league, same_window, pending)
    now = datetime.now(CN)
    if any(v.settled for v in verdicts.values()):
        structure = "high"
        risks.append(ParlayNote(
            key="lifecycle", level="high",
            message="包含已结算场次，体检只用于复盘，不代表赛前状态。"))
    elif any((k := _parse_kickoff(v.kickoff)) and k <= now for v in verdicts.values()):
        if structure == "low":
            structure = "medium"
        risks.append(ParlayNote(
            key="lifecycle", level="medium",
            message="包含已停售场次，体检只代表停售前数据。"))
    scores = ParlayScores(
        cost=_cost_level(cost_pct),
        info=_info_level(coverage_levels),
        model=_model_level(model_covered, len(legs)),
        structure=structure,
    )
    structure_label = {"low": "低", "medium": "中", "high": "高"}.get(structure, structure)
    full_info = sum(1 for x in coverage_levels if x == "full")
    summary = (f"成本 {cost:.2f} 元；信息 {full_info}/{len(legs)} 腿完整；"
               f"模型 {model_covered}/{len(legs)} 腿覆盖；结构{structure_label}风险。")
    # data_cutoff 取各腿 verdict payload 的截断时间；没有则留空。
    data_cutoffs = [((v.payload or {}).get("data_cutoff")) for v in verdicts.values()
                    if (v.payload or {}).get("data_cutoff")]
    return ParlayCheckResponse(
        legs=legs, combo=combo, scores=scores, risks=risks,
        optimizations=_optimizations(legs, cost), summary=summary,
        as_of=datetime.now(CN).isoformat(timespec="seconds"),
        data_cutoff=min(data_cutoffs) if data_cutoffs else None,
    )



_PICK_DIR = {"主胜": "home", "平局": "draw", "平": "draw", "客胜": "away"}
_RISK_LABEL = {"conservative": "保守型", "balanced": "均衡型", "aggressive": "进取型"}


def _pick_dir(v: Verdict) -> str | None:
    return _PICK_DIR.get(str((v.pick or {}).get("dir") or ""))


def _model_prob(v: Verdict, direction: str) -> float:
    attr = {"home": "model_h", "draw": "model_d", "away": "model_a"}[direction]
    try:
        return float(getattr(v, attr) or 0)
    except (TypeError, ValueError):
        return 0.0


def plan_parlay(db: Session, body: ParlayPlanRequest) -> ParlayPlanResponse:
    """从当日有明确方向的判决中生成 1–3 套参考组合；不调用 LLM。"""
    date = body.date or trade_date_now()
    try:
        trade_window(date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    rows = list(db.scalars(select(Verdict).where(Verdict.trade_date == date)).all())
    now = datetime.now(CN)
    candidates = []
    for v in rows:
        if v.status not in ("promoted", "screening") or v.settled:
            continue
        kickoff = _parse_kickoff(v.kickoff)
        if kickoff is not None and kickoff <= now:
            continue
        direction = _pick_dir(v)
        if direction is None:
            continue
        odds = _f(getattr(v, {"home": "sp_h", "draw": "sp_d", "away": "sp_a"}[direction]))
        rake = _f(v.rake)
        market_prob = _f(getattr(v, {"home": "p_home", "draw": "p_draw", "away": "p_away"}[direction]))
        if not odds or odds <= 1 or rake is None or market_prob is None:
            continue
        candidates.append({
            "verdict": v, "dir": direction, "odds": odds,
            "score": _model_prob(v, direction),
        })
    candidates.sort(key=lambda c: (-c["score"], c["verdict"].rake or 1))

    def choose(n: int) -> list[dict]:
        out = []
        for c in candidates:
            if c["verdict"].id in {x["verdict"].id for x in out}:
                continue
            out.append(c)
            if len(out) >= n:
                break
        return out

    sizes = {"conservative": 2, "balanced": 3, "aggressive": 3}
    plans: list[ParlayPlanItem] = []
    seen: set[tuple[str, ...]] = set()
    for profile in body.risk_profiles:
        size = sizes[profile]
        picked = choose(size)
        if len(picked) < 2:
            continue
        ids = tuple(c["verdict"].id for c in picked)
        if ids in seen:
            # 同一组腿不重复出两套；均衡型可尝试用前 2 腿。
            if profile == "balanced":
                picked = choose(2)
                ids = tuple(c["verdict"].id for c in picked)
            else:
                continue
        if ids in seen:
            continue
        seen.add(ids)
        try:
            check = check_parlay(db, ParlayCheckRequest(
                legs=[{"verdict_id": c["verdict"].id, "dir": c["dir"]} for c in picked],
                stake=body.stake))
        except HTTPException:
            continue
        note = None if len(picked) >= size else f"可用腿不足，按 {len(picked)} 腿生成"
        plans.append(ParlayPlanItem(
            label=_RISK_LABEL[profile], risk_profile=profile,
            legs=[c["verdict"].id for c in picked], check=check, note=note))

    message = None
    if not plans:
        message = "今日有明确方向的场次不足，先不配组合；可只看单场或等下一轮数据。"
    return ParlayPlanResponse(date=date, candidates=len(candidates),
                              plans=plans, message=message)
