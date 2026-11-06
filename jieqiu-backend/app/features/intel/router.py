"""聚焦决策流公开 API：数据脉搏 / 单场聚焦 / 互动埋点。"""
from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import InteractionEvent, User
from ...modules.users import is_deleted, user_from_token
from ..analysis import service as analysis_service
from . import service
from .schemas import (FocusResponse, InteractionResponse, MatchAnalysisResponse,
                      PulseResponse)

router = APIRouter(tags=["focus-intel"])

ALLOWED_EVENTS = {
    "focus_select", "action_click", "action_result", "free_text_open",
    "free_text_send", "pulse_open", "intel_expand", "source_open",
    "verdict_viewed", "plan_viewed",
}

_RATE_LOCK = threading.Lock()
_RATE: dict[str, list[float]] = {}
_RATE_WINDOW = 60.0
_RATE_MAX = 120


def optional_user(authorization: str | None = Header(default=None),
                  db: Session = Depends(get_db)) -> User | None:
    u = user_from_token(db, authorization)
    if u is None or is_deleted(u):
        return None
    return u


def _rate_ok(key: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        arr = [t for t in _RATE.get(key, []) if now - t < _RATE_WINDOW]
        if len(arr) >= _RATE_MAX:
            _RATE[key] = arr
            return False
        arr.append(now)
        _RATE[key] = arr
        if len(_RATE) > 5000:
            for old in list(_RATE)[:1000]:
                _RATE.pop(old, None)
        return True


class InteractionBody(BaseModel):
    event: str = Field(min_length=1, max_length=32)
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex,
                          min_length=8, max_length=64)
    schema_ver: int = Field(default=1, ge=1, le=10)
    session_id: str = Field(default="", max_length=64)
    match_id: str = Field(default="", max_length=32)
    verdict_id: str = Field(default="", max_length=40)
    action: str = Field(default="", max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/stats/pulse", response_model=PulseResponse)
def stats_pulse(date: str | None = None, db: Session = Depends(get_db)):
    """公开数据脉搏；只返回聚合，不含用户数据。"""
    try:
        return service.build_pulse(db, date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/matches/{match_id}/focus", response_model=FocusResponse)
def match_focus(match_id: str, response: Response, date: str | None = None,
                persona: str | None = None,
                user: User | None = Depends(optional_user),
                db: Session = Depends(get_db)):
    """单场聚焦：结论/三闸/覆盖率/客观情报/可用动作。"""
    if persona is not None and persona not in service.PERSONAS:
        raise HTTPException(422, "persona 必须是 zhuanjia/laopao/meng")
    try:
        payload = service.build_focus(db, match_id, date=date, persona=persona, user=user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if payload is None:
        raise HTTPException(404, "match not found")
    # capabilities 依赖登录态，禁止共享缓存。
    response.headers["Cache-Control"] = "private, no-store"
    return payload


@router.get("/matches/{match_id}/analysis",
            response_model=MatchAnalysisResponse)
def match_analysis(match_id: str, date: str | None = None,
                   db: Session = Depends(get_db)):
    """读取已缓存的单场 AI 解读；不触发 LLM。"""
    try:
        return analysis_service.get_cached(db, match_id, date=date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/matches/{match_id}/analysis",
             response_model=MatchAnalysisResponse)
def create_match_analysis(match_id: str, request: Request,
                          date: str | None = None,
                          user: User | None = Depends(optional_user),
                          db: Session = Depends(get_db)):
    """生成单场 AI 解读；同一事实包只调用一次 deep，失败返回 unavailable。"""
    rate_key = request.client.host if request.client else "anon"
    if not _rate_ok("analysis:" + rate_key):
        raise HTTPException(429, "解读请求过于频繁")
    try:
        return analysis_service.generate(db, match_id, date=date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/interactions", response_model=InteractionResponse)
def create_interaction(body: InteractionBody, request: Request,
                       user: User | None = Depends(optional_user),
                       db: Session = Depends(get_db)):
    """动作/聚焦漏斗埋点；幂等、白名单、无 PII。"""
    if body.event not in ALLOWED_EVENTS:
        raise HTTPException(422, "event 不在白名单")
    # 按 IP 限流，避免随机 session_id 绕过；同 IP 120/min 足够正常操作。
    rate_key = request.client.host if request.client else (body.session_id or "anon")
    if not _rate_ok(rate_key):
        raise HTTPException(429, "事件上报过于频繁")
    if len(json.dumps(body.metadata, ensure_ascii=False)) > 4096:
        raise HTTPException(422, "metadata 过大")
    existing = db.scalar(select(InteractionEvent).where(
        InteractionEvent.event_id == body.event_id))
    if existing is not None:
        return {"ok": True, "duplicate": True}
    row = InteractionEvent(
        event_id=body.event_id, schema_ver=body.schema_ver,
        user_id=user.id if user else None, session_id=body.session_id,
        event=body.event, match_id=body.match_id, verdict_id=body.verdict_id,
        action=body.action, metadata_json=body.metadata,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "duplicate": True}
    return {"ok": True, "duplicate": False}
