"""单场 AI 解读。

约束：
- 只基于 build_focus 已算出的事实包；不改写概率/方向、不新增数字。
- 只对 deep_eligible 的场次生成；同一事实包 hash 只调用一次 deep。
- 生成失败/无 Key/合规命中 → unavailable，调用方显示原因，不伪造解读。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import AIAnalysis
from ...modules import llm_gateway
from ...modules.compliance import scan_text
from ..intel import service as intel_service

PROMPT_VER = "match-analysis-v1"
_TTL_HOURS = 6
_MAX_FACTS = 14

_SYSTEM = (
    "你是球多多赛前数据解读助手。只根据用户给出的 fact pack 解释这场："
    "方向、成立条件、主要风险、失效条件和数据缺口。"
    "不得改写概率或方向，不得新增 fact pack 里没有的数字，不得承诺收益，"
    "不得使用任何绝对化、承诺性话术。事实不足就直说。"
    "只输出 JSON，不要 Markdown。"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_factors": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "invalidators": {"type": "array", "items": {"type": "string"}},
        "data_gaps": {"type": "array", "items": {"type": "string"}},
        "confidence_note": {"type": "string"},
    },
    "required": ["summary", "key_factors", "risks", "invalidators",
                 "data_gaps", "confidence_note"],
}
_LIST_FIELDS = ("key_factors", "risks", "invalidators", "data_gaps")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _compact(focus: dict) -> dict:
    verdict = focus.get("verdict") or {}
    facts = []
    for fact in (focus.get("intel") or {}).get("facts") or []:
        facts.append({
            "label": fact.get("label"),
            "value": fact.get("value"),
            "detail": fact.get("detail"),
            "status": fact.get("status"),
            "captured_at": fact.get("captured_at"),
        })
    coverage = focus.get("coverage") or {}
    return {
        "match": focus.get("match"),
        "data_cutoff": focus.get("data_cutoff"),
        "coverage": {
            "score": coverage.get("score"),
            "level": coverage.get("level"),
            "missing": coverage.get("missing") or [],
        },
        "verdict": {
            "status": verdict.get("status"),
            "pick": verdict.get("pick"),
            "probs": verdict.get("probs"),
            "gates": verdict.get("gates"),
            "rake": verdict.get("rake"),
            "rake_threshold": verdict.get("rake_threshold"),
        },
        "facts": facts[:_MAX_FACTS],
        "unknowns": (focus.get("intel") or {}).get("unknowns") or [],
    }


def _digest(compact: dict) -> str:
    body = json.dumps(compact, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256((PROMPT_VER + "|" + body).encode("utf-8")).hexdigest()


def _normalize(data: dict) -> dict | None:
    if not isinstance(data, dict):
        return None
    summary = str(data.get("summary") or "").strip()
    if not summary:
        return None
    out = {"summary": summary[:220]}
    for key in _LIST_FIELDS:
        values = data.get(key)
        if not isinstance(values, list):
            values = []
        out[key] = [str(v).strip()[:180] for v in values if str(v).strip()][:5]
    out["confidence_note"] = str(data.get("confidence_note") or "").strip()[:220]
    return out


def _ready(row: AIAnalysis, cached: bool) -> dict:
    payload = dict(row.payload or {})
    payload.update({
        "status": "ready",
        "model": row.model,
        "generated_at": row.created_at.isoformat() if row.created_at else None,
        "data_cutoff": row.data_cutoff,
        "cached": cached,
    })
    return payload


def _find(db: Session, match_id: str, digest: str) -> AIAnalysis | None:
    return db.scalar(select(AIAnalysis).where(
        AIAnalysis.match_id == match_id,
        AIAnalysis.input_hash == digest,
        AIAnalysis.status == "ok",
        AIAnalysis.expires_at > _utcnow(),
    ).order_by(AIAnalysis.id.desc()))


def cached_for_focus(db: Session, focus: dict) -> dict | None:
    """build_focus 用：只读缓存，绝不触发 LLM。"""
    try:
        compact = _compact(focus)
        digest = _digest(compact)
        row = _find(db, str((focus.get("match") or {}).get("match_id") or ""),
                    digest)
        return _ready(row, cached=True) if row is not None else None
    except Exception:  # noqa: BLE001 - 解读缓存不能拖垮聚焦接口
        return None


def get_cached(db: Session, match_id: str, date: str | None = None) -> dict:
    focus = intel_service.build_focus(db, match_id, date=date, user=None)
    if focus is None:
        return {"status": "unavailable", "reason": "match_not_found"}
    analysis = cached_for_focus(db, focus)
    if analysis is None:
        return {"status": "unavailable", "reason": "not_generated"}
    return analysis


def generate(db: Session, match_id: str, date: str | None = None,
             force: bool = False) -> dict:
    focus = intel_service.build_focus(db, match_id, date=date, user=None)
    if focus is None:
        return {"status": "unavailable", "reason": "match_not_found"}
    coverage = focus.get("coverage") or {}
    if not coverage.get("deep_eligible"):
        return {
            "status": "unavailable",
            "reason": "coverage",
            "missing": coverage.get("missing") or [],
        }
    compact = _compact(focus)
    digest = _digest(compact)
    existing = _find(db, match_id, digest)
    if existing is not None and not force:
        return _ready(existing, cached=True)

    result = llm_gateway.complete(
        db, "match_analysis",
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(
                compact, ensure_ascii=False, sort_keys=True)},
        ],
        schema=_SCHEMA, max_tokens=1200, temperature=0.2,
    )
    if result.degraded:
        return {"status": "unavailable", "reason": result.error_class or "degraded"}
    data = _normalize(result.data or {})
    if data is None:
        return {"status": "unavailable", "reason": "invalid_output"}
    all_text = " ".join([data["summary"], *data["key_factors"], *data["risks"],
                         *data["invalidators"], *data["data_gaps"],
                         data["confidence_note"]])
    if scan_text(all_text):
        return {"status": "unavailable", "reason": "compliance"}

    now = _utcnow()
    expires = now + timedelta(hours=_TTL_HOURS)
    row = db.scalar(select(AIAnalysis).where(
        AIAnalysis.match_id == match_id,
        AIAnalysis.input_hash == digest,
    ).order_by(AIAnalysis.id.desc()))
    if row is None:
        row = AIAnalysis(match_id=match_id, input_hash=digest)
        db.add(row)
    row.trade_date = str(focus.get("trade_date") or "")
    row.data_cutoff = focus.get("data_cutoff")
    row.status = "ok"
    row.payload = data
    row.model = result.model
    row.provider = result.provider
    row.prompt_ver = PROMPT_VER
    row.created_at = now
    row.expires_at = expires
    db.commit()
    return _ready(row, cached=False)
