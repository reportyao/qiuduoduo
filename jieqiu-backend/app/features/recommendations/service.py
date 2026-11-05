"""推荐主链：Decision Snapshot → AI Review → Publish Lifecycle。

事实源仍是 verdict（三闸/封存）；本服务不再生成第二套方向，只把“这次对外
要表达的判断”固化为不可变 snapshot，并让 Today Hero / 组合 / 付费 / 复盘
都消费同一个 snapshot_id。
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...models import (DecisionSnapshot, RecommendationEvent, RecommendationPlan,
                       ReviewRun, Verdict, utcnow)
from ...modules import llm_gateway
from ...modules.compliance import scan_text
from ...modules.timeutil import CN, trade_date_now
from ..tools import service as parlay_service
from ..tools.schemas import ParlayPlanRequest

logger = logging.getLogger(__name__)
SNAP_SCHEMA = "decision-snapshot/v1"
PLAN_SCHEMA = "recommendation-plan/v1"
REVIEW_PROMPT_VER = "review-v1"

DRAFT = "draft"
REVIEWING = "reviewing"
APPROVED = "approved"
REVIEW_FAILED = "review_failed"
PUBLISHED = "published"
EXPIRED = "expired"
WITHDRAWN = "withdrawn"

SUBJECT_DECISION = "decision"
SUBJECT_PLAN = "plan"

_ACTIVE = {DRAFT, REVIEWING, APPROVED, REVIEW_FAILED, PUBLISHED}
_DIRECTIONS = {"home": "主胜", "draw": "平局", "away": "客胜",
               "主胜": "主胜", "平局": "平局", "客胜": "客胜"}


def _now_cn() -> datetime:
    return datetime.now(CN).replace(tzinfo=None)


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)


def _hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _parse_kickoff(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:19].replace("T", " "),
                                 "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _verdict_card(v: Verdict) -> dict:
    """与 /stream 的判决卡同形；Today Hero 可直接复用移动端 adapter。"""
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
        "gates": {k: (g or {}).get("result", "unknown")
                  for k, g in (v.gates or {}).items()},
        "hash": v.payload_hash,
        "sealed": v.sealed_at is not None,
        "model": (v.payload or {}).get("model") or {},
    }


def _conditions(v: Verdict) -> list[str]:
    gates = v.gates or {}
    out: list[str] = []
    if (gates.get("price") or {}).get("result") == "pass":
        out.append(f"抽水不高于 {v.rake_threshold * 100:.1f}%")
    if (gates.get("market") or {}).get("result") == "pass":
        out.append("国际盘与竞彩去水概率的离散度在阈值内")
    if (gates.get("model") or {}).get("result") == "pass":
        out.append("模型置信达到可推线，且已向市场概率收缩")
    return out or ["三闸未同时通过，只能作为观察项"]


def _invalidators(v: Verdict) -> list[str]:
    return [
        f"抽水回升到 {v.rake_threshold * 100:.1f}% 以上",
        "临场国际盘反向，离散度超过阈值",
        "首发/伤停变化导致模型方向反转",
        "停售前价格快速回落，成本优势消失",
    ]


def _snapshot_payload(v: Verdict) -> dict:
    return {
        "schema": SNAP_SCHEMA,
        "verdict": _verdict_card(v),
        "direction": (v.pick or {}).get("dir") or "观望",
        "conditions": _conditions(v),
        "invalidators": _invalidators(v),
        "source": {
            "verdict_id": v.id,
            "verdict_hash": v.payload_hash,
            "data_cutoff": (v.payload or {}).get("data_cutoff"),
        },
    }


def _latest_decision(db: Session, date: str, match_id: str) -> DecisionSnapshot | None:
    return db.scalar(select(DecisionSnapshot)
                     .where(DecisionSnapshot.trade_date == date,
                            DecisionSnapshot.match_id == match_id)
                     .order_by(DecisionSnapshot.version.desc()))


def _latest_plan(db: Session, date: str, profile: str) -> RecommendationPlan | None:
    return db.scalar(select(RecommendationPlan)
                     .where(RecommendationPlan.trade_date == date,
                            RecommendationPlan.risk_profile == profile)
                     .order_by(RecommendationPlan.version.desc()))


def _event(db: Session, subject_type: str, subject_id: str, action: str,
           from_status: str, to_status: str, actor: str = "pipeline",
           note: str = "") -> None:
    db.add(RecommendationEvent(
        subject_type=subject_type, subject_id=subject_id, action=action,
        from_status=from_status, to_status=to_status, actor=actor, note=note))


def build_snapshots(db: Session, date: str | None = None,
                    actor: str = "pipeline") -> list[DecisionSnapshot]:
    """把当日 promoted verdict 固化为 draft snapshot；源哈希不变不重复建版本。"""
    date = date or trade_date_now()
    now = _now_cn()
    rows = list(db.scalars(select(Verdict).where(Verdict.trade_date == date)).all())
    out: list[DecisionSnapshot] = []
    for v in rows:
        if v.status != "promoted" or v.settled or not v.pick:
            continue
        kick = _parse_kickoff(v.kickoff)
        if kick is not None and kick <= now:
            continue
        payload = _snapshot_payload(v)
        payload_hash = _hash(payload)
        source_hash = v.payload_hash or _hash(payload)
        latest = _latest_decision(db, date, v.match_id)
        if latest is not None and latest.source_hash == source_hash:
            out.append(latest)
            continue
        if latest is not None and latest.status in _ACTIVE:
            old_status = latest.status
            latest.status = EXPIRED
            latest.updated_at = utcnow()
            _event(db, SUBJECT_DECISION, latest.id, "expire", old_status, EXPIRED,
                   actor, "new source version")
        version = (latest.version + 1) if latest is not None else 1
        snap = DecisionSnapshot(
            id=uuid.uuid4().hex,
            trade_date=date,
            match_id=v.match_id,
            match_no=v.match_no,
            verdict_id=v.id,
            version=version,
            status=DRAFT,
            payload=payload,
            payload_hash=payload_hash,
            source_hash=source_hash,
            expires_at=kick,
        )
        db.add(snap)
        db.flush()
        _event(db, SUBJECT_DECISION, snap.id, "build", "", DRAFT, actor)
        out.append(snap)
    db.commit()
    return out


def _plan_expiry(db: Session, legs: list[str]) -> datetime | None:
    if not legs:
        return None
    rows = list(db.scalars(select(Verdict).where(Verdict.id.in_(legs))).all())
    kicks = [_parse_kickoff(v.kickoff) for v in rows]
    kicks = [k for k in kicks if k is not None]
    return min(kicks) if kicks else None


def build_plans(db: Session, date: str | None = None, stake: float = 100,
                actor: str = "pipeline") -> list[RecommendationPlan]:
    """把确定性组合参谋结果固化为 draft；legs/check 不变不重复建版本。"""
    date = date or trade_date_now()
    try:
        result = parlay_service.plan_parlay(
            db, ParlayPlanRequest(date=date, stake=stake))
    except Exception:  # noqa: BLE001 - 单日组合失败不能拖垮整条 seed/pipeline
        logger.exception("build_plans failed date=%s", date)
        return []
    out: list[RecommendationPlan] = []
    for item in result.plans:
        payload = {
            "schema": PLAN_SCHEMA,
            "label": item.label,
            "risk_profile": item.risk_profile,
            "legs": item.legs,
            "note": item.note,
            "conditions": [
                "所有腿在停售前保持 promoted",
                "组合模型覆盖保持完整",
                "任一腿价格/闸门失效则组合失效",
            ],
            "invalidators": [
                "任一腿停售、结算或降级为 screening/killed",
                "组合模型覆盖不再完整",
                "同联赛/同开赛时间导致相关性上升",
            ],
            "check": item.check.model_dump(mode="json"),
        }
        payload_hash = _hash(payload)
        source_hash = payload_hash
        latest = _latest_plan(db, date, item.risk_profile)
        if latest is not None and latest.source_hash == source_hash:
            out.append(latest)
            continue
        if latest is not None and latest.status in _ACTIVE:
            old_status = latest.status
            latest.status = EXPIRED
            latest.updated_at = utcnow()
            _event(db, SUBJECT_PLAN, latest.id, "expire", old_status, EXPIRED,
                   actor, "new source version")
        version = (latest.version + 1) if latest is not None else 1
        row = RecommendationPlan(
            id=uuid.uuid4().hex,
            trade_date=date,
            risk_profile=item.risk_profile,
            version=version,
            status=DRAFT,
            label=item.label,
            legs=item.legs,
            payload=payload,
            payload_hash=payload_hash,
            source_hash=source_hash,
            expires_at=_plan_expiry(db, item.legs),
        )
        db.add(row)
        db.flush()
        _event(db, SUBJECT_PLAN, row.id, "build", "", DRAFT, actor)
        out.append(row)
    db.commit()
    return out


def _get_subject(db: Session, subject_type: str, subject_id: str):
    if subject_type == SUBJECT_DECISION:
        return db.get(DecisionSnapshot, subject_id)
    if subject_type == SUBJECT_PLAN:
        return db.get(RecommendationPlan, subject_id)
    raise ValueError("unknown subject_type")


def _llm_review(db: Session, subject_type: str, payload: dict) -> tuple[dict, bool, str]:
    """可选 deep/fast 复核；无 Key/超预算/失败不阻塞规则门，但会标记降级。"""
    task = "plan_review" if subject_type == SUBJECT_PLAN else "decision_review"
    body = _canonical(payload)[:12000]
    result = llm_gateway.complete(
        db, task,
        [
            {"role": "system", "content": (
                "你是发布前复核器。只检查给定 canonical payload 是否有事实矛盾、"
                "数字越界、过度承诺、缺失失效条件。不要新增观点。"
                "只输出 JSON：{\"verdict\":\"pass|fail\",\"issues\":[\"...\"]}。")},
            {"role": "user", "content": body},
        ],
        schema={
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["pass", "fail"]},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["verdict"],
        },
        max_tokens=400,
        temperature=0.1,
    )
    if result.degraded:
        return ({"name": "llm_review", "status": "skip",
                 "detail": result.error_class or "degraded", "required": False}, True,
                result.error_class or "degraded")
    data = result.data or {}
    passed = data.get("verdict") == "pass"
    return ({"name": "llm_review", "status": "pass" if passed else "fail",
             "detail": data.get("issues") or [], "model": result.model,
             "required": False}, False, result.model)


def _layer(name: str, passed: bool, detail, *, required: bool = True) -> dict:
    return {"name": name, "status": "pass" if passed else "fail",
            "detail": detail, "required": required}


def review_subject(db: Session, subject_type: str, subject_id: str,
                   actor: str = "pipeline") -> ReviewRun:
    """L1 规则 / L2 事实数字 / L3 人设 / L4 对抗 / L5 发布门 + 可选 LLM。"""
    subject = _get_subject(db, subject_type, subject_id)
    if subject is None:
        raise ValueError("subject not found")
    if subject.status in (EXPIRED, WITHDRAWN):
        raise ValueError("subject is not reviewable")
    subject.status = REVIEWING
    payload = subject.payload or {}
    layers: list[dict] = []

    # L1 规则：禁用词、必填结构
    hit = scan_text(_canonical(payload))
    required_ok = (payload.get("schema") in (SNAP_SCHEMA, PLAN_SCHEMA)
                   and bool(payload.get("direction") if subject_type == SUBJECT_DECISION
                            else payload.get("legs")))
    cutoff_ok = True
    if subject_type == SUBJECT_DECISION:
        source = payload.get("source") or {}
        cutoff = _parse_kickoff(source.get("data_cutoff"))
        cutoff_ok = cutoff is not None and (_now_cn() - cutoff) <= timedelta(hours=24)
    layers.append(_layer("L1_rules", not hit and required_ok and cutoff_ok,
                         {"banned": hit, "schema_ok": required_ok,
                          "cutoff_ok": cutoff_ok}))

    # L2 事实/数字
    if subject_type == SUBJECT_DECISION:
        card = payload.get("verdict") or {}
        sp = card.get("sp") or {}
        probs = card.get("probs") or {}
        odds_ok = all(isinstance(sp.get(k), (int, float)) and sp[k] > 1
                      for k in ("h", "d", "a"))
        prob_sum = sum(float(probs.get(k) or 0) for k in ("home", "draw", "away"))
        dir_ok = (payload.get("direction") in _DIRECTIONS)
        source = payload.get("source") or {}
        source_ok = bool(source.get("verdict_id") and source.get("verdict_hash"))
        layers.append(_layer("L2_facts",
                             odds_ok and 0.9 <= prob_sum <= 1.1 and dir_ok and source_ok,
                             {"odds_ok": odds_ok, "prob_sum": round(prob_sum, 4),
                              "direction": payload.get("direction"),
                              "source_ok": source_ok}))
    else:
        check = payload.get("check") or {}
        combo = check.get("combo") or {}
        legs = payload.get("legs") or []
        odds_ok = float(combo.get("odds") or 0) > 1
        cost_ok = float(combo.get("cost") or -1) >= 0
        layers.append(_layer("L2_facts", len(legs) >= 2 and odds_ok and cost_ok,
                             {"legs": len(legs), "odds": combo.get("odds"),
                              "cost": combo.get("cost")}))

    # L3 人设：canonical snapshot 不内嵌自由文案；有 copy 才检查
    copy = payload.get("copy") or payload.get("persona_copy") or ""
    copy_ok = True
    if copy:
        copy_ok = len(str(copy)) <= 600 and not scan_text(str(copy))
    layers.append(_layer("L3_persona", copy_ok,
                         {"copy_present": bool(copy), "length": len(str(copy))}))

    # L4 对抗：必须写清条件与失效条件
    if subject_type == SUBJECT_DECISION:
        cond = payload.get("conditions") or []
        invalid = payload.get("invalidators") or []
        layers.append(_layer("L4_adversarial", bool(cond) and bool(invalid),
                             {"conditions": len(cond), "invalidators": len(invalid)}))
    else:
        invalid = payload.get("invalidators") or []
        risks = (payload.get("check") or {}).get("risks") or []
        layers.append(_layer("L4_adversarial", bool(invalid) or bool(risks),
                             {"invalidators": len(invalid), "risks": len(risks)}))

    # L5 发布门：已封存、未结算、未停售；组合每腿必须 promoted 且模型全覆
    if subject_type == SUBJECT_DECISION:
        card = payload.get("verdict") or {}
        kick = _parse_kickoff(card.get("kickoff"))
        gates = card.get("gates") or {}
        gates_ok = bool(gates) and all(v == "pass" for v in gates.values())
        sealed_ok = bool(card.get("sealed"))
        future_ok = kick is not None and kick > _now_cn()
        layers.append(_layer("L5_publish_gate",
                             gates_ok and sealed_ok and future_ok,
                             {"gates": gates, "sealed": sealed_ok,
                              "kickoff": card.get("kickoff")}))
    else:
        check = payload.get("check") or {}
        legs = check.get("legs") or []
        legs_ok = bool(legs) and all(
            leg.get("status") == "promoted" and leg.get("sealed")
            for leg in legs)
        coverage_ok = (check.get("combo") or {}).get("model_coverage") == f"{len(legs)}/{len(legs)}"
        layers.append(_layer("L5_publish_gate", legs_ok and coverage_ok,
                             {"legs_ok": legs_ok, "coverage": coverage_ok}))

    llm_layer, llm_degraded, reviewer_tail = _llm_review(db, subject_type, payload)
    layers.append(llm_layer)
    required_ok = all(l["status"] == "pass" for l in layers if l.get("required", True))
    llm_ok = next((l for l in layers if l.get("name") == "llm_review"), {}).get("status") != "fail"
    status = "passed" if required_ok and llm_ok else "failed"
    run = ReviewRun(
        subject_type=subject_type, subject_id=subject_id, status=status,
        layers=layers, reviewer="rules" if llm_degraded else f"rules+{reviewer_tail}",
        prompt_ver=REVIEW_PROMPT_VER, llm_degraded=llm_degraded,
    )
    db.add(run)
    db.flush()
    subject.review_run_id = run.id
    subject.status = APPROVED if status == "passed" else REVIEW_FAILED
    subject.updated_at = utcnow()
    _event(db, subject_type, subject_id, "review", REVIEWING, subject.status,
           actor, status)
    db.commit()
    return run


def _publishable(subject) -> None:
    if subject.status != APPROVED:
        raise ValueError("subject is not approved")
    if subject.review_run_id is None:
        raise ValueError("missing review run")


def publish_subject(db: Session, subject_type: str, subject_id: str,
                    actor: str = "pipeline") -> object:
    subject = _get_subject(db, subject_type, subject_id)
    if subject is None:
        raise ValueError("subject not found")
    _publishable(subject)
    run = db.get(ReviewRun, subject.review_run_id)
    if run is None or run.status != "passed":
        raise ValueError("review did not pass")
    expires = subject.expires_at or _plan_expiry(db, subject.legs) \
        if subject_type == SUBJECT_PLAN else subject.expires_at
    if expires is None:
        raise ValueError("missing expiry")
    if expires <= _now_cn():
        raise ValueError("subject already expired")
    old = subject.status
    subject.status = PUBLISHED
    subject.published_at = utcnow()
    subject.expires_at = expires
    subject.updated_at = utcnow()
    _event(db, subject_type, subject_id, "publish", old, PUBLISHED, actor)
    db.commit()
    return subject


def withdraw_subject(db: Session, subject_type: str, subject_id: str,
                     reason: str = "", actor: str = "console") -> object:
    subject = _get_subject(db, subject_type, subject_id)
    if subject is None:
        raise ValueError("subject not found")
    if subject.status not in (APPROVED, PUBLISHED, REVIEW_FAILED):
        raise ValueError("subject is not withdrawable")
    old = subject.status
    subject.status = WITHDRAWN
    subject.withdrawn_at = utcnow()
    subject.updated_at = utcnow()
    _event(db, subject_type, subject_id, "withdraw", old, WITHDRAWN, actor, reason)
    db.commit()
    return subject


def expire_due(db: Session, date: str | None = None, actor: str = "pipeline") -> int:
    now = _now_cn()
    q = select(DecisionSnapshot).where(DecisionSnapshot.status == PUBLISHED,
                                      DecisionSnapshot.expires_at.isnot(None),
                                      DecisionSnapshot.expires_at <= now)
    if date:
        q = q.where(DecisionSnapshot.trade_date == date)
    rows = list(db.scalars(q).all())
    q2 = select(RecommendationPlan).where(RecommendationPlan.status == PUBLISHED,
                                         RecommendationPlan.expires_at.isnot(None),
                                         RecommendationPlan.expires_at <= now)
    if date:
        q2 = q2.where(RecommendationPlan.trade_date == date)
    plans = list(db.scalars(q2).all())
    for row in [*rows, *plans]:
        st = SUBJECT_DECISION if isinstance(row, DecisionSnapshot) else SUBJECT_PLAN
        row.status = EXPIRED
        row.updated_at = utcnow()
        _event(db, st, row.id, "expire", PUBLISHED, EXPIRED, actor)
    if rows or plans:
        db.commit()
    return len(rows) + len(plans)


def run_pipeline(db: Session, date: str | None = None, stake: float = 100,
                 actor: str = "pipeline") -> dict:
    date = date or trade_date_now()
    expired = expire_due(db, date, actor)
    snaps = build_snapshots(db, date, actor)
    plans = build_plans(db, date, stake, actor)
    reviewed = passed = published = 0
    for subject_type, rows in ((SUBJECT_DECISION, snaps), (SUBJECT_PLAN, plans)):
        for row in rows:
            if row.status in (DRAFT, REVIEW_FAILED):
                run = review_subject(db, subject_type, row.id, actor)
                reviewed += 1
                if run.status == "passed":
                    passed += 1
            if row.status == APPROVED:
                try:
                    publish_subject(db, subject_type, row.id, actor)
                    published += 1
                except ValueError:
                    pass
    return {"date": date, "snapshots": len(snaps), "plans": len(plans),
            "reviewed": reviewed, "approved": passed, "published": published,
            "expired": expired}


def _review_public(db: Session, subject_type: str, subject_id: str,
                   review_run_id: int | None = None) -> dict | None:
    """公开复核徽章：只暴露状态/复核人/时间/层结果，不暴露 prompt 细节。"""
    run = db.get(ReviewRun, review_run_id) if review_run_id else db.scalar(
        select(ReviewRun).where(ReviewRun.subject_type == subject_type,
                                ReviewRun.subject_id == subject_id)
        .order_by(ReviewRun.id.desc()))
    if run is None:
        return None
    return {
        "status": run.status,
        "reviewer": run.reviewer,
        "reviewed_at": run.created_at.isoformat() if run.created_at else None,
        "prompt_ver": run.prompt_ver,
        "llm_degraded": bool(run.llm_degraded),
        "layers": run.layers or [],
    }


def _public_snapshot(db: Session, row: DecisionSnapshot) -> dict:
    payload = row.payload or {}
    verdict = payload.get("verdict") or {}
    pick = verdict.get("pick") or {}
    confidence = pick.get("prob") if isinstance(pick, dict) else None
    return {
        "snapshot_id": row.id,
        "trade_date": row.trade_date,
        "match_id": row.match_id,
        "status": row.status,
        "version": row.version,
        "payload_hash": row.payload_hash,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "verdict": verdict,
        "direction": payload.get("direction") or "观望",
        "confidence": float(confidence) if confidence is not None else None,
        "prob_low": None,
        "prob_high": None,
        "conditions": payload.get("conditions") or [],
        "invalidators": payload.get("invalidators") or [],
        "review": _review_public(db, SUBJECT_DECISION, row.id, row.review_run_id),
    }


def _public_plan(db: Session, row: RecommendationPlan) -> dict:
    payload = row.payload or {}
    return {
        "plan_id": row.id,
        "trade_date": row.trade_date,
        "risk_profile": row.risk_profile,
        "label": row.label,
        "legs": row.legs or [],
        "status": row.status,
        "version": row.version,
        "payload_hash": row.payload_hash,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "check": payload.get("check") or {},
        "note": payload.get("note"),
        "conditions": payload.get("conditions") or [],
        "invalidators": payload.get("invalidators") or [],
        "review": _review_public(db, SUBJECT_PLAN, row.id, row.review_run_id),
    }


def today(db: Session, date: str | None = None) -> dict:
    """只读：过期由 cron 的 expire_due 处理，GET 不写库。"""
    date = date or trade_date_now()
    now = _now_cn()
    not_expired_snap = or_(DecisionSnapshot.expires_at.is_(None),
                           DecisionSnapshot.expires_at > now)
    not_expired_plan = or_(RecommendationPlan.expires_at.is_(None),
                           RecommendationPlan.expires_at > now)
    snaps = list(db.scalars(
        select(DecisionSnapshot).where(
            DecisionSnapshot.trade_date == date,
            DecisionSnapshot.status == PUBLISHED,
            not_expired_snap)
        .order_by(DecisionSnapshot.match_no, DecisionSnapshot.version)).all())
    plans = list(db.scalars(
        select(RecommendationPlan).where(
            RecommendationPlan.trade_date == date,
            RecommendationPlan.status == PUBLISHED,
            not_expired_plan)
        .order_by(RecommendationPlan.risk_profile, RecommendationPlan.version)).all())
    message = None
    if not snaps and not plans:
        verdicts = list(db.scalars(select(Verdict).where(Verdict.trade_date == date)).all())
        pending = 0
        for v in verdicts:
            gate = (v.gates or {}).get("market") or {}
            result = gate.get("result") if isinstance(gate, dict) else gate
            if result == "pending_data":
                pending += 1
        if not verdicts:
            message = "今日暂无已发布判断；采集或判决数据还没到。"
        elif pending >= len(verdicts):
            message = "今日暂无已发布判断；国际盘数据未接入或覆盖不足，市闸无法通过，今天不硬推。"
        else:
            message = "今日暂无已发布判断；复核中或数据不足。"
    return {
        "trade_date": date,
        "generated_at": _now_cn().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshots": [_public_snapshot(db, s) for s in snaps],
        "plans": [_public_plan(db, p) for p in plans],
        "verdicts": [(s.payload or {}).get("verdict") or {} for s in snaps],
        "message": message,
    }
