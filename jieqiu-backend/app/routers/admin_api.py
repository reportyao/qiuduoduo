"""新版管理后台 JSON API。

前端位于 `app/static/admin/`；认证使用 `admin_t` HttpOnly 会话 + RBAC。
这个路由只提供管理面数据/动作，不对外暴露任何 Key 或原始用户数据。
"""
from __future__ import annotations

import ipaddress
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..features.recommendations import service as recommendation_service
from ..features.tools import service as parlay_service
from ..features.tools.schemas import ParlayPlanRequest
from ..models import (AdminAudit, AdminUser, ApiFootballFixture,
                      DecisionSnapshot, InteractionEvent, LLMProfile, CollectorStatus,
                      Notification, PersonaLLMModel, PushToken,
                      RecommendationEvent, RecommendationPlan, ReviewRun,
                      SPSnapshot, Verdict)
from ..modules import admin_auth, api_football, llm_gateway, persona_llm, persona_registry, supply
from ..modules.sealchain import latest_chain_status
from ..modules.timeutil import CN, trade_date_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-ui"],
                   dependencies=[Depends(admin_auth.csrf_guard)])
STATIC_DIR = Path(__file__).resolve().parents[1] / "static" / "admin"
LOG_FILES = {
    "sync": "sync.log",
    "recommendations": "recommendations.log",
    "persona": "persona.log",
    "assistant": "assistant.log",
    "purge": "purge.log",
    "db_maint": "db_maint.log",
    "backtest": "backtest.log",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _push_channel_status() -> dict:
    configured = bool(os.environ.get("JQ_JPUSH_APPKEY")
                      and os.environ.get("JQ_JPUSH_MASTER_SECRET"))
    dryrun = (os.environ.get("JQ_JPUSH_DRYRUN", "").strip() in ("1", "true", "yes")
              or not configured)
    return {"provider": "jpush", "configured": configured, "dryrun": dryrun}


def _model(row: PersonaLLMModel) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "base_url": row.base_url,
        "model": row.model,
        "priority": row.priority,
        "enabled": row.enabled,
        "key": persona_llm.mask_key(row.api_key_enc),
        "timeout_s": row.timeout_s,
        "max_tokens": row.max_tokens,
        "temperature": row.temperature,
        "fail_count": row.fail_count,
        "last_error": persona_llm._scrub_error(row.last_error) if row.last_error else None,
        "last_error_at": _iso(row.last_error_at),
        "last_ok_at": _iso(row.last_ok_at),
        "healthy": row.enabled and row.fail_count < 3,
    }


def _snapshot(row: DecisionSnapshot) -> dict:
    payload = row.payload or {}
    card = payload.get("verdict") or {}
    return {
        "id": row.id,
        "trade_date": row.trade_date,
        "match_id": row.match_id,
        "verdict_id": row.verdict_id,
        "version": row.version,
        "status": row.status,
        "match_no": row.match_no,
        "league": card.get("league") or "",
        "home": card.get("home") or "",
        "away": card.get("away") or "",
        "kickoff": card.get("kickoff") or "",
        "direction": payload.get("direction") or "—",
        "conditions": payload.get("conditions") or [],
        "invalidators": payload.get("invalidators") or [],
        "gates": card.get("gates") or {},
        "sealed": bool(card.get("sealed")),
        "payload_hash": row.payload_hash,
        "review_run_id": row.review_run_id,
        "published_at": _iso(row.published_at),
        "expires_at": _iso(row.expires_at),
        "created_at": _iso(row.created_at),
    }


def _plan(row: RecommendationPlan) -> dict:
    payload = row.payload or {}
    check = payload.get("check") or {}
    return {
        "id": row.id,
        "trade_date": row.trade_date,
        "risk_profile": row.risk_profile,
        "version": row.version,
        "status": row.status,
        "label": row.label,
        "legs": row.legs or [],
        "combo": check.get("combo") or {},
        "scores": check.get("scores") or {},
        "risks": check.get("risks") or [],
        "conditions": payload.get("conditions") or [],
        "invalidators": payload.get("invalidators") or [],
        "review_run_id": row.review_run_id,
        "published_at": _iso(row.published_at),
        "expires_at": _iso(row.expires_at),
        "created_at": _iso(row.created_at),
    }


def _review(row: ReviewRun | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "status": row.status,
        "layers": row.layers or [],
        "reviewer": row.reviewer,
        "prompt_ver": row.prompt_ver,
        "llm_degraded": row.llm_degraded,
        "created_at": _iso(row.created_at),
    }


def _count(db: Session, model, *conditions) -> int:
    q = select(func.count()).select_from(model)
    if conditions:
        q = q.where(*conditions)
    return int(db.scalar(q) or 0)


def _valid_date(value: str | None) -> str:
    date = value or trade_date_now()
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise HTTPException(400, "date 必须是 YYYY-MM-DD")
    return date


def _sync_lag(db: Session) -> tuple[str | None, int | None]:
    latest = db.scalar(select(func.max(SPSnapshot.captured_at)))
    if not latest:
        return None, None
    try:
        dt = datetime.fromisoformat(str(latest))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CN)
        return str(latest), max(0, int((datetime.now(CN) - dt).total_seconds()))
    except (TypeError, ValueError):
        return str(latest), None


def _tail_log(name: str, lines: int = 160) -> list[str]:
    filename = LOG_FILES.get(name)
    if not filename:
        raise HTTPException(404, "log not found")
    path = Path.cwd() / filename
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            # 从尾部读 256KB，避免把几百 MB 日志全量读进内存。
            f.seek(max(0, size - 256 * 1024))
            raw = f.read().decode("utf-8", errors="ignore")
        rows = raw.splitlines()
        if size > 256 * 1024 and rows:
            rows = rows[1:]  # 第一行可能被截断
        return rows[-max(1, min(lines, 500)):]
    except OSError:
        return []


@router.get("", include_in_schema=False)
def admin_shell():
    return FileResponse(STATIC_DIR / "index.html", headers={
        "Cache-Control": "no-cache",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        ),
    })


def _audit(db: Session, principal: admin_auth.AdminPrincipal, action: str,
           target_type: str = "", target_id: str = "",
           before: dict | None = None, after: dict | None = None,
           request: Request | None = None) -> None:
    """写操作审计；失败不覆盖主操作结果，只记录日志。"""
    try:
        db.add(AdminAudit(
            actor=principal.username, role=principal.role, action=action,
            target_type=target_type, target_id=str(target_id),
            before_json=before, after_json=after,
            ip=(request.client.host if request and request.client else ""),
        ))
        db.commit()
    except Exception:  # noqa: BLE001 - 审计失败不能回滚已完成的业务动作
        db.rollback()
        logger.exception("admin audit failed action=%s target=%s", action, target_id)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


@router.post("/api/login")
def admin_login(body: LoginBody, response: Response, request: Request,
                db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '?'}:{body.username.strip().lower()}"
    if admin_auth.login_locked(key):
        raise HTTPException(429, "尝试过多，请 10 分钟后再试",
                            headers={"Retry-After": "600"})
    user = admin_auth.authenticate(db, body.username, body.password)
    if user is None:
        admin_auth.record_login_fail(key)
        _audit(db, admin_auth.AdminPrincipal(id=0, username=body.username[:64],
                                             role="unknown"),
               "login.failed", "admin_user", body.username[:64],
               after={"reason": "bad_credentials"}, request=request)
        raise HTTPException(401, "用户名或密码错误")
    admin_auth.clear_login_fail(key)
    token, ttl = admin_auth.create_session(user)
    csrf = admin_auth._SESSIONS.get(token, {}).get("csrf", "")
    _audit(db, admin_auth.AdminPrincipal(id=user.id, username=user.username,
                                         role=user.role),
           "login", "admin_user", user.id, request=request)
    secure = get_settings().admin_cookie_secure
    response.set_cookie(
        admin_auth.SESSION_COOKIE, token, httponly=True, max_age=ttl,
        samesite="strict", secure=secure,
    )
    response.set_cookie(
        "admin_csrf", csrf, httponly=False, max_age=ttl,
        samesite="strict", secure=secure,
    )
    return {"authenticated": True, "username": user.username, "role": user.role,
            "csrf_token": csrf, "env": get_settings().env, "date": trade_date_now()}


@router.post("/api/logout")
def admin_logout(request: Request, response: Response,
                 db: Session = Depends(get_db)):
    principal = admin_auth.optional_admin(request)
    if principal is not None:
        _audit(db, principal, "logout", "admin_user", principal.id, request=request)
    admin_auth.revoke_session(request.cookies.get(admin_auth.SESSION_COOKIE))
    response.delete_cookie(admin_auth.SESSION_COOKIE)
    response.delete_cookie("admin_csrf")
    return {"ok": True}


@router.get("/api/session")
def admin_session(request: Request):
    principal = admin_auth.optional_admin(request)
    info = admin_auth.session_info(request) or {}
    return {"authenticated": principal is not None,
            "username": principal.username if principal else "",
            "role": principal.role if principal else "",
            "csrf_token": info.get("csrf", ""),
            "env": get_settings().env, "date": trade_date_now()}


@router.get("/assets/{filename}", include_in_schema=False)
def admin_asset(filename: str):
    # 只允许白名单内的静态资源，杜绝路径穿越/任意文件读取。
    safe = Path(filename).name
    if safe not in {"admin.css", "admin.js", "admin_extra.js"}:
        raise HTTPException(404)
    path = (STATIC_DIR / safe).resolve()
    if not path.is_file() or STATIC_DIR.resolve() not in path.parents:
        raise HTTPException(404)
    media = "text/css" if path.suffix == ".css" else "application/javascript"
    return FileResponse(path, media_type=f"{media}; charset=utf-8", headers={
        "Cache-Control": "no-cache",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/api/overview")
def admin_overview(db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    date = trade_date_now()
    today_promoted = _count(db, Verdict, Verdict.trade_date == date,
                            Verdict.status == "promoted")
    today_screening = _count(db, Verdict, Verdict.trade_date == date,
                             Verdict.status == "screening")
    today_killed = _count(db, Verdict, Verdict.trade_date == date,
                          Verdict.status == "killed")
    snapshot_statuses = dict(db.execute(
        select(DecisionSnapshot.status, func.count())
        .where(DecisionSnapshot.trade_date == date)
        .group_by(DecisionSnapshot.status)).all())
    plan_statuses = dict(db.execute(
        select(RecommendationPlan.status, func.count())
        .where(RecommendationPlan.trade_date == date)
        .group_by(RecommendationPlan.status)).all())
    models = persona_llm.list_models(db)
    latest_snapshot = db.scalar(select(DecisionSnapshot)
                                .order_by(DecisionSnapshot.created_at.desc()))
    latest_event = db.scalar(select(RecommendationEvent)
                             .order_by(RecommendationEvent.id.desc()))
    latest_verdict = db.scalar(select(Verdict).order_by(Verdict.created_at.desc()))
    sync_latest, sync_lag = _sync_lag(db)
    degraded_models = [m for m in models if m.enabled and m.fail_count >= 3]
    unconfigured_profiles = [p for p in llm_gateway.profile_status(db)
                           if not p["configured"] and p.get("enabled", True)]

    def total_status(status: str) -> int:
        return snapshot_statuses.get(status, 0) + plan_statuses.get(status, 0)

    actions = []
    if total_status("draft"):
        actions.append({"kind": "review", "severity": "high",
                        "label": f"{total_status('draft')} 条待复核",
                        "detail": "草稿还没过 AI Review，不会进入用户端",
                        "view": "recommendations", "filter": "draft"})
    if total_status("review_failed"):
        actions.append({"kind": "review_failed", "severity": "high",
                        "label": f"{total_status('review_failed')} 条复核失败",
                        "detail": "检查 L1–L5 失败层，修正后重新复核",
                        "view": "recommendations", "filter": "review_failed"})
    if total_status("approved"):
        actions.append({"kind": "publish", "severity": "medium",
                        "label": f"{total_status('approved')} 条已过审待发布",
                        "detail": "复核通过但尚未对用户可见",
                        "view": "recommendations", "filter": "approved"})
    if degraded_models:
        actions.append({"kind": "model", "severity": "high",
                        "label": f"{len(degraded_models)} 个模型降级",
                        "detail": "连续失败 ≥3 次，检查 Key/上游或切换优先级",
                        "view": "models", "filter": "all"})
    if sync_lag is not None and sync_lag > 1800:
        actions.append({"kind": "data", "severity": "high",
                        "label": "SP 数据超过 30 分钟未更新",
                        "detail": f"最新快照 {sync_latest}，检查采集器/SFTP/cron",
                        "view": "data", "filter": "all"})
    if unconfigured_profiles:
        actions.append({"kind": "keys", "severity": "low",
                        "label": f"{len(unconfigured_profiles)} 个模型配置未配 Key",
                        "detail": "未配置时该任务会自动降级到模板/固定引导",
                        "view": "gateway", "filter": "all"})
    return {
        "date": date,
        "env": get_settings().env,
        "counts": {
            "verdicts_today": {"promoted": today_promoted,
                               "screening": today_screening,
                               "killed": today_killed,
                               "total": today_promoted + today_screening + today_killed},
            "snapshots": snapshot_statuses,
            "plans": plan_statuses,
            "reviews": {
                "total": _count(db, ReviewRun),
                "passed": _count(db, ReviewRun, ReviewRun.status == "passed"),
                "failed": _count(db, ReviewRun, ReviewRun.status == "failed"),
            },
            "models": {
                "total": len(models),
                "enabled": sum(1 for m in models if m.enabled),
                "configured": sum(1 for m in models if m.api_key_enc),
                "degraded": sum(1 for m in models if m.fail_count >= 3),
            },
        },
        "models": [_model(m) for m in models],
        "latest": {
            "snapshot_created_at": _iso(latest_snapshot.created_at) if latest_snapshot else None,
            "event_at": _iso(latest_event.created_at) if latest_event else None,
            "verdict_created_at": _iso(latest_verdict.created_at) if latest_verdict else None,
        },
        "sync": {"latest": sync_latest, "lag_seconds": sync_lag},
        "actions": actions,
        "gateway": llm_gateway.usage_summary(db),
        "gateway_profiles": llm_gateway.profile_status(db),
        "push_channel": _push_channel_status(),
        "push_tokens": {
            "total": _count(db, PushToken),
            "enabled": _count(db, PushToken, PushToken.enabled.is_(True)),
        },
    }


@router.get("/api/models")
def admin_models(db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    persona_llm.ensure_default_models(db)
    return {"models": [_model(m) for m in persona_llm.list_models(db)]}


class ModelUpsert(BaseModel):
    name: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    priority: int = Field(default=100, ge=1, le=9999)
    timeout_s: int = Field(default=20, ge=3, le=120)
    max_tokens: int = Field(default=800, ge=64, le=4096)
    temperature: float = Field(default=0.4, ge=0, le=1.5)
    enabled: bool = True


class ModelPatch(BaseModel):
    name: str | None = None
    base_url: str | None = None
    model: str | None = None
    priority: int | None = Field(default=None, ge=1, le=9999)
    enabled: bool | None = None
    timeout_s: int | None = Field(default=None, ge=3, le=120)
    max_tokens: int | None = Field(default=None, ge=64, le=4096)
    temperature: float | None = Field(default=None, ge=0, le=1.5)
    reset_failures: bool = False


class KeyPatch(BaseModel):
    api_key: str


class PersonaTest(BaseModel):
    persona: Literal["zhuanjia", "laopao", "meng"] = "zhuanjia"
    text: str = Field(min_length=1, max_length=1000)


@router.post("/api/models")
def admin_create_model(body: ModelUpsert, request: Request,
                       db: Session = Depends(get_db),
                       principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    try:
        row = persona_llm.add_model(
            db, name=body.name, base_url=body.base_url, model=body.model,
            api_key=body.api_key, priority=body.priority,
            timeout_s=body.timeout_s, max_tokens=body.max_tokens,
            temperature=body.temperature)
    except persona_llm.PersonaLLMError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "model.create", "model", row.id,
           after=_model(row), request=request)
    return {"model": _model(row)}


@router.patch("/api/models/{model_id}")
def admin_update_model(model_id: int, body: ModelPatch, request: Request,
                       db: Session = Depends(get_db),
                       principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise HTTPException(404, "model not found")
    before = _model(row)
    if body.name is not None:
        row.name = body.name.strip()[:64]
    if body.base_url is not None:
        if not body.base_url.startswith(("http://", "https://")):
            raise HTTPException(400, "base_url 必须是 http(s)")
        row.base_url = body.base_url.strip().rstrip("/")[:256]
    if body.model is not None:
        if not body.model.strip():
            raise HTTPException(400, "model 不能为空")
        row.model = body.model.strip()[:96]
    if body.priority is not None:
        row.priority = body.priority
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.timeout_s is not None:
        row.timeout_s = body.timeout_s
    if body.max_tokens is not None:
        row.max_tokens = body.max_tokens
    if body.temperature is not None:
        row.temperature = body.temperature
    if body.reset_failures:
        row.fail_count = 0
        row.last_error = None
        row.last_error_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "同一 base_url + model 已存在")
    db.refresh(row)
    _audit(db, principal, "model.update", "model", row.id,
           before=before, after=_model(row), request=request)
    return {"model": _model(row)}


@router.delete("/api/models/{model_id}")
def admin_delete_model(model_id: int, request: Request,
                       db: Session = Depends(get_db),
                       principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise HTTPException(404, "model not found")
    before = _model(row)
    persona_llm.delete_model(db, model_id)
    _audit(db, principal, "model.delete", "model", model_id,
           before=before, request=request)
    return {"ok": True}


@router.post("/api/models/{model_id}/key")
def admin_update_model_key(model_id: int, body: KeyPatch, request: Request,
                           db: Session = Depends(get_db),
                           principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    try:
        row = persona_llm.update_key(db, model_id, body.api_key)
    except persona_llm.PersonaLLMError as exc:
        raise HTTPException(404, str(exc))
    _audit(db, principal, "model.key_update", "model", row.id,
           after={"key": _model(row)["key"]}, request=request)
    return {"model": _model(row)}


@router.post("/api/models/{model_id}/test")
def admin_test_model(model_id: int, body: PersonaTest, request: Request,
                     db: Session = Depends(get_db),
                     principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    """只测试指定模型本身（不走 failover 池），用于验证单个 Key/模型是否可用。"""
    row = db.get(PersonaLLMModel, model_id)
    if row is None:
        raise HTTPException(404, "model not found")
    try:
        content, _usage, latency = persona_llm._call_model(row, body.text, body.persona, db=db)
        _audit(db, principal, "model.test", "model", row.id,
               after={"ok": True, "latency_ms": latency}, request=request)
        return {"ok": True, "model": row.model, "persona": body.persona,
                "latency_ms": latency, "text": content}
    except persona_llm.PersonaLLMError as exc:
        _audit(db, principal, "model.test", "model", row.id,
               after={"ok": False}, request=request)
        return {"ok": False, "model": row.model,
                "error": persona_llm._scrub_error(str(exc))}


@router.post("/api/persona/test")
def admin_persona_test(body: PersonaTest, request: Request,
                       db: Session = Depends(get_db),
                       principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    try:
        result = persona_llm.translate(db, body.text, body.persona, use_cache=False)
        _audit(db, principal, "persona.test", "persona", body.persona,
               after={"ok": True, "latency_ms": result.latency_ms}, request=request)
        return {"ok": True, "model": result.model, "persona": result.persona,
                "latency_ms": result.latency_ms, "text": result.text}
    except persona_llm.PersonaLLMError as exc:
        return {"ok": False, "error": persona_llm._scrub_error(str(exc))}


@router.get("/api/personas")
def admin_personas(db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    persona_registry.ensure_seeded(db)
    profiles = persona_registry.list_profiles(db)
    slots = persona_registry.list_slots(db)
    return {
        "profiles": [{
            "id": p.id, "name": p.name, "address": p.address, "tone": p.tone,
            "style_prompt": p.style_prompt, "max_chars": p.max_chars,
            "emoji_policy": p.emoji_policy, "allowed_emoji": p.allowed_emoji,
            "version": p.version, "enabled": p.enabled, "updated_at": _iso(p.updated_at),
        } for p in profiles],
        "slots": [{
            "id": s.id, "persona_id": s.persona_id, "slot_key": s.slot_key,
            "template": s.template, "version": s.version, "enabled": s.enabled,
            "updated_at": _iso(s.updated_at),
        } for s in slots],
        "slot_keys": list(persona_registry.DEFAULT_SLOTS),
    }


class ProfilePatch(BaseModel):
    name: str | None = None
    address: str | None = None
    tone: str | None = None
    style_prompt: str | None = None
    max_chars: int | None = Field(default=None, ge=60, le=600)
    emoji_policy: Literal["none", "limited", "free"] | None = None
    allowed_emoji: str | None = None
    enabled: bool | None = None


class SlotPatch(BaseModel):
    template: str = Field(max_length=2000)
    enabled: bool = True


@router.put("/api/personas/{persona_id}")
def admin_update_persona(persona_id: str, body: ProfilePatch, request: Request,
                         db: Session = Depends(get_db),
                         principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    row = persona_registry.get_profile(db, persona_id)
    if row is None:
        raise HTTPException(404, "persona not found")
    before = {"address": row.address, "tone": row.tone, "max_chars": row.max_chars,
              "emoji_policy": row.emoji_policy, "enabled": row.enabled,
              "version": row.version}
    if body.name is not None:
        row.name = body.name.strip()[:32]
    if body.address is not None:
        row.address = body.address.strip()[:16]
    if body.tone is not None:
        row.tone = body.tone.strip()[:64]
    if body.style_prompt is not None:
        row.style_prompt = body.style_prompt.strip()[:1200]
    if body.max_chars is not None:
        row.max_chars = body.max_chars
    if body.emoji_policy is not None:
        row.emoji_policy = body.emoji_policy
    if body.allowed_emoji is not None:
        row.allowed_emoji = body.allowed_emoji.strip()[:32]
    if body.enabled is not None:
        row.enabled = body.enabled
    row.version += 1
    db.commit()
    db.refresh(row)
    _audit(db, principal, "persona.update", "persona", persona_id,
           before=before,
           after={"address": row.address, "tone": row.tone,
                  "max_chars": row.max_chars, "emoji_policy": row.emoji_policy,
                  "enabled": row.enabled, "version": row.version},
           request=request)
    return {"ok": True, "version": row.version}


@router.put("/api/personas/{persona_id}/slots/{slot_key}")
def admin_update_slot(persona_id: str, slot_key: str, body: SlotPatch,
                      request: Request, db: Session = Depends(get_db),
                      principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    try:
        row = persona_registry.update_slot(db, persona_id, slot_key, body.template)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    row.enabled = body.enabled
    db.commit()
    db.refresh(row)
    _audit(db, principal, "persona.slot_update", "persona_slot",
           f"{persona_id}:{slot_key}", after={"version": row.version,
                                              "enabled": row.enabled},
           request=request)
    return {"ok": True, "version": row.version}


@router.get("/api/recommendations")
def admin_recommendations(date: str | None = None, limit: int = 50,
                          offset: int = 0,
                          db: Session = Depends(get_db),
                          _: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("viewer"))):
    date = _valid_date(date)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    snap_total = _count(db, DecisionSnapshot, DecisionSnapshot.trade_date == date)
    snaps = list(db.scalars(select(DecisionSnapshot)
                            .where(DecisionSnapshot.trade_date == date)
                            .order_by(DecisionSnapshot.match_no,
                                      DecisionSnapshot.version.desc())
                            .limit(limit).offset(offset)).all())
    plans = list(db.scalars(select(RecommendationPlan)
                            .where(RecommendationPlan.trade_date == date)
                            .order_by(RecommendationPlan.risk_profile,
                                      RecommendationPlan.version.desc())).all())
    ids = {row.id for row in snaps} | {row.id for row in plans}
    events = list(db.scalars(select(RecommendationEvent)
                             .order_by(RecommendationEvent.id.desc()).limit(40)).all())
    runs = list(db.scalars(select(ReviewRun)
                           .where(ReviewRun.subject_id.in_(ids))
                           .order_by(ReviewRun.id.desc())).all()) if ids else []
    latest_runs = {}
    for run in runs:
        latest_runs.setdefault(run.subject_id, _review(run))
    return {
        "date": date,
        "snapshots": [_snapshot(row) for row in snaps],
        "plans": [_plan(row) for row in plans],
        "reviews": latest_runs,
        "events": [{
            "id": e.id, "subject_type": e.subject_type, "subject_id": e.subject_id,
            "action": e.action, "from_status": e.from_status, "to_status": e.to_status,
            "actor": e.actor, "note": e.note, "created_at": _iso(e.created_at),
        } for e in events],
        "counts": {
            "snapshots": snap_total,
            "plans": len(plans),
            "published": (
                _count(db, DecisionSnapshot,
                       DecisionSnapshot.trade_date == date,
                       DecisionSnapshot.status == "published")
                + _count(db, RecommendationPlan,
                         RecommendationPlan.trade_date == date,
                         RecommendationPlan.status == "published")),
            "review_failed": (
                _count(db, DecisionSnapshot,
                       DecisionSnapshot.trade_date == date,
                       DecisionSnapshot.status == "review_failed")
                + _count(db, RecommendationPlan,
                         RecommendationPlan.trade_date == date,
                         RecommendationPlan.status == "review_failed")),
        },
        "page": {"limit": limit, "offset": offset, "total": snap_total,
                 "has_more": offset + len(snaps) < snap_total,
                 "next_offset": offset + len(snaps)},
    }


class PipelineRun(BaseModel):
    date: str | None = None
    stake: float = Field(default=100, ge=1, le=1_000_000)


class SubjectAction(BaseModel):
    reason: str = Field(default="", max_length=500)


@router.post("/api/recommendations/run")
def admin_run_pipeline(body: PipelineRun, request: Request,
                       db: Session = Depends(get_db),
                       principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    result = recommendation_service.run_pipeline(
        db, date=_valid_date(body.date), stake=body.stake,
        actor=principal.username)
    _audit(db, principal, "recommendation.run", "pipeline",
           result.get("date", ""), after=result, request=request)
    return result


class BatchAction(BaseModel):
    action: Literal["review", "publish"]
    date: str | None = None
    limit: int = Field(default=200, ge=1, le=500)


@router.post("/api/recommendations/batch")
def admin_batch_recommendations(body: BatchAction, request: Request,
                                db: Session = Depends(get_db),
                                principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    """OPC 批量操作：只处理当前日期、符合状态的 draft/approved。"""
    date = _valid_date(body.date)
    snaps = list(db.scalars(select(DecisionSnapshot)
                            .where(DecisionSnapshot.trade_date == date)
                            .order_by(DecisionSnapshot.id).limit(body.limit)).all())
    plans = list(db.scalars(select(RecommendationPlan)
                            .where(RecommendationPlan.trade_date == date)
                            .order_by(RecommendationPlan.id).limit(body.limit)).all())
    done = 0
    errors: list[str] = []
    for subject_type, rows in (("decision", snaps), ("plan", plans)):
        for row in rows:
            if body.action == "review":
                if row.status not in ("draft", "review_failed"):
                    continue
                try:
                    recommendation_service.review_subject(db, subject_type, row.id,
                                                          actor=principal.username)
                    done += 1
                except ValueError as exc:
                    errors.append(f"{subject_type}:{row.id}: {exc}")
                except Exception as exc:  # noqa: BLE001 - 单条失败不阻断批量
                    errors.append(f"{subject_type}:{row.id}: {type(exc).__name__}")
            else:
                if row.status != "approved":
                    continue
                try:
                    recommendation_service.publish_subject(db, subject_type, row.id,
                                                           actor=principal.username)
                    done += 1
                except ValueError as exc:
                    errors.append(f"{subject_type}:{row.id}: {exc}")
                except Exception as exc:  # noqa: BLE001 - 单条失败不阻断批量
                    errors.append(f"{subject_type}:{row.id}: {type(exc).__name__}")
    skipped = len(snaps) + len(plans) - done - len(errors)
    result = {"date": date, "action": body.action, "done": done,
              "skipped": max(0, skipped), "errors": errors[:20]}
    _audit(db, principal, f"recommendation.batch_{body.action}",
           "recommendation", date, after=result, request=request)
    return result


@router.post("/api/recommendations/{subject_type}/{subject_id}/review")
def admin_review_subject(subject_type: Literal["decision", "plan"], subject_id: str,
                         request: Request, db: Session = Depends(get_db),
                         principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    try:
        run = recommendation_service.review_subject(db, subject_type, subject_id,
                                                    actor=principal.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "recommendation.review", subject_type, subject_id,
           after={"review_id": run.id, "status": run.status}, request=request)
    return {"review": _review(run)}


@router.post("/api/recommendations/{subject_type}/{subject_id}/publish")
def admin_publish_subject(subject_type: Literal["decision", "plan"], subject_id: str,
                          request: Request, db: Session = Depends(get_db),
                          principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    try:
        recommendation_service.publish_subject(db, subject_type, subject_id,
                                               actor=principal.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "recommendation.publish", subject_type, subject_id,
           after={"status": "published"}, request=request)
    return {"ok": True}


@router.post("/api/recommendations/{subject_type}/{subject_id}/withdraw")
def admin_withdraw_subject(subject_type: Literal["decision", "plan"], subject_id: str,
                           body: SubjectAction, request: Request,
                           db: Session = Depends(get_db),
                           principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("operator"))):
    try:
        recommendation_service.withdraw_subject(db, subject_type, subject_id,
                                                body.reason, principal.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "recommendation.withdraw", subject_type, subject_id,
           after={"status": "withdrawn", "reason": body.reason}, request=request)
    return {"ok": True}


@router.get("/api/plans-preview")
def admin_plans_preview(date: str | None = None, stake: float = 100,
                        db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    try:
        result = parlay_service.plan_parlay(db, ParlayPlanRequest(
            date=_valid_date(date), stake=stake))
        return result.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - 预览失败返回业务错误
        raise HTTPException(400, str(exc))


@router.get("/api/gateway")
def admin_gateway(db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    summary = llm_gateway.usage_summary(db)
    return {
        "profiles": llm_gateway.profile_status(db),
        "routes": llm_gateway.TASK_PROFILE,
        "summary": summary,
    }


_LLM_PURPOSE = {
    "fast": "对话问答 / 轻任务（/chat 开放问题、组合复核）",
    "deep": "发布前复核 / 单场深读（决策复核、未来实时分析）",
}


def _validate_llm_base_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(400, "Base URL 必须是 https:// 开头的完整地址")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise HTTPException(400, "Base URL 不允许指向本机/内网")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local
                           or ip.is_reserved or ip.is_multicast):
        raise HTTPException(400, "Base URL 不允许指向内网/保留地址")
    return url


def _llm_profile_view(name: str, db: Session) -> dict:
    row = db.get(LLMProfile, name)
    effective = next(p for p in llm_gateway.profile_status(db) if p["name"] == name)
    return {
        "name": name,
        "purpose": _LLM_PURPOSE.get(name, ""),
        "provider": effective["provider"],
        "base_url": effective["base_url"],
        "model": effective["model"],
        "configured": effective["configured"],
        "source": effective["source"],  # admin | env | none
        "enabled": effective.get("enabled", True),
        "input_price_cny_per_m": effective["input_price_cny_per_m"],
        "output_price_cny_per_m": effective["output_price_cny_per_m"],
        "admin_key_set": bool(row and row.api_key_enc),
        "updated_at": _iso(row.updated_at) if row else None,
    }


class LLMProfileUpdate(BaseModel):
    provider: str = Field(default="openai_compatible", max_length=32)
    base_url: str = Field(min_length=8, max_length=256)
    model: str = Field(min_length=1, max_length=96)
    api_key: str | None = Field(default=None, max_length=512)
    clear_key: bool = False
    input_price_cny_per_m: float = Field(default=0, ge=0, le=10000)
    output_price_cny_per_m: float = Field(default=0, ge=0, le=10000)
    enabled: bool = True


@router.get("/api/llm/profiles")
def admin_llm_profiles(db: Session = Depends(get_db),
                       _: None = Depends(admin_auth.require_role("viewer"))):
    return {"profiles": [_llm_profile_view(name, db)
                         for name in llm_gateway.LLM_PROFILE_NAMES]}


@router.put("/api/llm/profiles/{name}")
def admin_llm_profile_update(name: str, body: LLMProfileUpdate, request: Request,
                             db: Session = Depends(get_db),
                             principal: admin_auth.AdminPrincipal = Depends(
                                 admin_auth.require_role("admin"))):
    if name not in llm_gateway.LLM_PROFILE_NAMES:
        raise HTTPException(404, "未知的 LLM 能力")
    base_url = _validate_llm_base_url(body.base_url)
    row = db.get(LLMProfile, name)
    if row is None:
        row = LLMProfile(name=name)
        db.add(row)
    before = _llm_profile_view(name, db)
    row.provider = body.provider.strip()[:32] or "openai_compatible"
    row.base_url = base_url
    row.model = body.model.strip()
    row.input_price_cny_per_m = body.input_price_cny_per_m
    row.output_price_cny_per_m = body.output_price_cny_per_m
    row.enabled = body.enabled
    if body.clear_key:
        row.api_key_enc = ""
    elif body.api_key is not None and body.api_key.strip():
        row.api_key_enc = persona_llm.encrypt_key(body.api_key.strip())
    db.commit()
    after = _llm_profile_view(name, db)
    _audit(db, principal, "llm.profile.update", "llm_profile", name,
           before=before, after=after, request=request)
    return {"profile": after}


@router.post("/api/llm/profiles/{name}/test")
def admin_llm_profile_test(name: str, request: Request,
                           db: Session = Depends(get_db),
                           principal: admin_auth.AdminPrincipal = Depends(
                               admin_auth.require_role("operator"))):
    if name not in llm_gateway.LLM_PROFILE_NAMES:
        raise HTTPException(404, "未知的 LLM 能力")
    profile = llm_gateway._profile(name, db)
    if not profile.get("api_key") or not profile.get("enabled", True):
        raise HTTPException(400, "该能力尚未配置可用的 API Key")
    started = datetime.now(timezone.utc)
    try:
        text, usage = llm_gateway.call_profile(
            profile,
            [{"role": "user", "content": "只回复两个字：正常"}],
            max_tokens=32, temperature=0, timeout_s=15,
        )
    except Exception as exc:  # noqa: BLE001 - 测试失败原样返回给管理员
        _audit(db, principal, "llm.profile.test", "llm_profile", name,
               after={"ok": False}, request=request)
        raise HTTPException(400, f"调用失败：{str(exc)[:240]}")
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    _audit(db, principal, "llm.profile.test", "llm_profile", name,
           after={"ok": True, "model": profile["model"]}, request=request)
    return {
        "ok": True,
        "provider": profile["provider"],
        "model": profile["model"],
        "latency_ms": latency_ms,
        "text": (text or "").strip()[:200],
        "usage": usage,
    }


def _collector_view(db: Session) -> dict:
    row = db.get(CollectorStatus, 1)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data_path = get_settings().collector_data_path
    data_updated = None
    data_age = None
    try:
        mtime = datetime.fromtimestamp(Path(data_path).stat().st_mtime, timezone.utc).replace(tzinfo=None)
        data_updated = _iso(mtime)
        data_age = int((now - mtime).total_seconds())
    except OSError:
        pass
    if row is None:
        return {"state": "never", "online": False, "last_seen": None,
                "stale_seconds": None, "last_success_at": None,
                "last_error": "", "cycle": 0, "matches": 0,
                "snapshots_total": 0, "last_push_at": None,
                "restart_pending": False, "host": "", "pid": "",
                "version": "", "data_updated_at": data_updated,
                "data_age_seconds": data_age}
    stale = int((now - row.last_seen).total_seconds()) if row.last_seen else None
    online = stale is not None and stale <= 600
    return {
        "state": "online" if online else "stale",
        "online": online,
        "last_seen": _iso(row.last_seen),
        "stale_seconds": stale,
        "last_success_at": _iso(row.last_success_at),
        "last_error": row.last_error or "",
        "cycle": row.cycle,
        "matches": row.matches,
        "snapshots_total": row.snapshots_total,
        "last_push_at": _iso(row.last_push_at),
        "restart_pending": row.restart_requested_at is not None,
        "restart_requested_at": _iso(row.restart_requested_at),
        "host": row.host,
        "pid": row.pid,
        "version": row.version,
        "data_updated_at": data_updated,
        "data_age_seconds": data_age,
    }


@router.get("/api/collector")
def admin_collector(db: Session = Depends(get_db),
                    _: None = Depends(admin_auth.require_role("viewer"))):
    return _collector_view(db)


@router.post("/api/collector/restart")
def admin_collector_restart(request: Request,
                            db: Session = Depends(get_db),
                            principal: admin_auth.AdminPrincipal = Depends(
                                admin_auth.require_role("operator"))):
    row = db.get(CollectorStatus, 1)
    if row is None:
        raise HTTPException(409, "采集器从未上报心跳，无法下发重启")
    row.restart_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    _audit(db, principal, "collector.restart", "collector", "1",
           after={"requested_at": _iso(row.restart_requested_at)}, request=request)
    return _collector_view(db)


@router.get("/api/data")
def admin_data(db: Session = Depends(get_db), _: None = Depends(admin_auth.require_role("viewer"))):
    date = trade_date_now()
    af = api_football.status(db)
    sync_latest, sync_lag = _sync_lag(db)
    return {
        "date": date,
        "sync": {"latest": sync_latest, "lag_seconds": sync_lag},
        "verdicts": {
            "total": _count(db, Verdict),
            "promoted": _count(db, Verdict, Verdict.status == "promoted"),
            "screening": _count(db, Verdict, Verdict.status == "screening"),
            "killed": _count(db, Verdict, Verdict.status == "killed"),
            "today": _count(db, Verdict, Verdict.trade_date == date),
        },
        "snapshots": {
            "total": _count(db, SPSnapshot),
            "latest": db.scalar(select(SPSnapshot.captured_at)
                                .order_by(SPSnapshot.captured_at.desc())),
        },
        "api_football": af,
        "supply": supply.content_supply(db, date),
    }


@router.get("/api/logs")
def admin_logs(name: str = "sync", lines: int = 120,
               _: None = Depends(admin_auth.require_role("viewer"))):
    return {"name": name, "lines": _tail_log(name, lines)}


class FootballLink(BaseModel):
    fixture_id: int = Field(ge=1)
    match_id: str = Field(min_length=1, max_length=32)


@router.post("/api/football/link")
def admin_football_link(body: FootballLink, request: Request,
                        db: Session = Depends(get_db),
                        principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    try:
        api_football.link_fixture(db, body.fixture_id, body.match_id.strip())
    except api_football.ApiFootballError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "football.link", "fixture", body.fixture_id,
           after={"match_id": body.match_id.strip()}, request=request)
    return {"ok": True}


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["viewer", "operator", "admin"] = "operator"


class AdminUserPatch(BaseModel):
    role: Literal["viewer", "operator", "admin"] | None = None
    enabled: bool | None = None


class AdminPasswordPatch(BaseModel):
    password: str = Field(min_length=8, max_length=200)


def _admin_user(row: AdminUser) -> dict:
    return {"id": row.id, "username": row.username, "role": row.role,
            "enabled": row.enabled, "created_at": _iso(row.created_at),
            "last_login_at": _iso(row.last_login_at)}


@router.get("/api/users")
def admin_users(db: Session = Depends(get_db),
                _: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    return {"users": [_admin_user(u) for u in admin_auth.list_users(db)]}


@router.post("/api/users")
def admin_create_user(body: AdminUserCreate, request: Request,
                      db: Session = Depends(get_db),
                      principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    try:
        user = admin_auth.create_user(db, body.username, body.password, body.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _audit(db, principal, "user.create", "admin_user", user.id,
           after=_admin_user(user), request=request)
    return {"user": _admin_user(user)}


@router.patch("/api/users/{user_id}")
def admin_update_user(user_id: int, body: AdminUserPatch, request: Request,
                      db: Session = Depends(get_db),
                      principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    before = _admin_user(user)
    next_role = body.role if body.role is not None else user.role
    next_enabled = body.enabled if body.enabled is not None else user.enabled
    if user.id == principal.id and (next_role != "admin" or not next_enabled):
        raise HTTPException(400, "不能降级或停用当前登录账号")
    if user.role == "admin" and (next_role != "admin" or not next_enabled):
        admin_count = int(db.scalar(select(func.count()).select_from(AdminUser)
                                    .where(AdminUser.role == "admin",
                                           AdminUser.enabled.is_(True))) or 0)
        if admin_count <= 1:
            raise HTTPException(400, "至少保留一个启用的 admin")
    user.role = next_role
    user.enabled = next_enabled
    db.commit()
    db.refresh(user)
    revoked = admin_auth.revoke_all_for_user(user.id)
    _audit(db, principal, "user.update", "admin_user", user.id,
           before=before, after={**_admin_user(user), "revoked_sessions": revoked},
           request=request)
    return {"user": _admin_user(user), "revoked_sessions": revoked}


@router.post("/api/users/{user_id}/password")
def admin_reset_user_password(user_id: int, body: AdminPasswordPatch,
                              request: Request, db: Session = Depends(get_db),
                              principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    user.password_hash = admin_auth.hash_password(body.password)
    db.commit()
    revoked = admin_auth.revoke_all_for_user(user.id)
    _audit(db, principal, "user.password_reset", "admin_user", user.id,
           after={"username": user.username, "revoked_sessions": revoked},
           request=request)
    return {"ok": True, "revoked_sessions": revoked}


@router.delete("/api/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db),
                      principal: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("admin"))):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if user.id == principal.id:
        raise HTTPException(400, "不能删除当前登录账号")
    if user.role == "admin":
        admin_count = int(db.scalar(select(func.count()).select_from(AdminUser)
                                    .where(AdminUser.role == "admin",
                                           AdminUser.enabled.is_(True))) or 0)
        if admin_count <= 1:
            raise HTTPException(400, "至少保留一个启用的 admin")
    before = _admin_user(user)
    db.delete(user)
    db.commit()
    revoked = admin_auth.revoke_all_for_user(user_id)
    _audit(db, principal, "user.delete", "admin_user", user_id,
           before=before, after={"revoked_sessions": revoked}, request=request)
    return {"ok": True, "revoked_sessions": revoked}


@router.get("/api/audit")
def admin_audit(limit: int = 50, offset: int = 0,
                db: Session = Depends(get_db),
                _: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("viewer"))):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = _count(db, AdminAudit)
    rows = list(db.scalars(select(AdminAudit).order_by(AdminAudit.id.desc())
                           .limit(limit).offset(offset)).all())
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "next_offset": offset + len(rows),
        "items": [{
            "id": r.id, "actor": r.actor, "role": r.role, "action": r.action,
            "target_type": r.target_type, "target_id": r.target_id,
            "before": r.before_json, "after": r.after_json, "ip": r.ip,
            "created_at": _iso(r.created_at),
        } for r in rows],
    }


@router.get("/api/ops")
def admin_ops(db: Session = Depends(get_db),
              _: admin_auth.AdminPrincipal = Depends(admin_auth.require_role("viewer"))):
    """运维聚合：告警、API-Football、封存链、通知、Push、互动与推荐覆盖。"""
    date = trade_date_now()
    sync_latest, sync_lag = _sync_lag(db)
    chain = latest_chain_status(db)
    notif = dict(db.execute(select(Notification.status, func.count())
                            .group_by(Notification.status)).all())
    interaction_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    interaction_rows = dict(db.execute(
        select(InteractionEvent.event, func.count())
        .where(InteractionEvent.created_at >= interaction_since)
        .group_by(InteractionEvent.event)).all())
    football = api_football.status(db)
    supply_data = supply.content_supply(db, date)
    snap_count = _count(db, DecisionSnapshot, DecisionSnapshot.trade_date == date)
    plan_count = _count(db, RecommendationPlan, RecommendationPlan.trade_date == date)
    failed = _count(db, DecisionSnapshot, DecisionSnapshot.trade_date == date,
                    DecisionSnapshot.status == "review_failed")
    failed += _count(db, RecommendationPlan, RecommendationPlan.trade_date == date,
                     RecommendationPlan.status == "review_failed")
    alerts = []
    if sync_lag is None or sync_lag > 1800:
        alerts.append({"level": "high", "title": "SP 数据不可用或延迟",
                       "detail": f"最新 {sync_latest or '—'} · lag {sync_lag if sync_lag is not None else '—'}"})
    if not chain.get("ok", True):
        alerts.append({"level": "high", "title": "封存链异常",
                       "detail": f"broken_at={chain.get('broken_at')}"})
    if failed:
        alerts.append({"level": "high", "title": f"{failed} 条复核失败",
                       "detail": "去推荐主链检查 L1–L5"})
    if not football.get("configured"):
        alerts.append({"level": "low", "title": "API-Football 未配置",
                       "detail": "阵容/伤停/积分榜将保持 missing"})
    elif football.get("warnings"):
        alerts.append({"level": "medium", "title": "API-Football 覆盖不完整",
                       "detail": "；".join(football["warnings"])})
    intl = supply_data["intl_odds"]
    if not intl["configured"] and supply_data["matches"] > 0:
        alerts.append({"level": "high", "title": "国际盘未配置（The Odds API）",
                       "detail": "市闸需要 ≥2 个去水口径；未配置时全部判决停在 pending_data，推荐主链不会产出"})
    elif intl["total"] == 0 and supply_data["matches"] > 0:
        alerts.append({"level": "high", "title": "国际盘 0 条",
                       "detail": f"今日 {supply_data['matches']} 场，但 intl_odds 为空；检查 JQ_ODDS_API_KEY 与同步日志"})
    elif intl["covered_matches"] == 0 and supply_data["matches"] > 0:
        alerts.append({"level": "high", "title": "今日国际盘未覆盖任何场次",
                       "detail": f"intl_odds 有 {intl['total']} 行，但今日 {supply_data['matches']} 场都没匹配上；检查队名对齐/开赛时间/源覆盖"})
    if (supply_data["verdicts"]["total"] > 0
            and supply_data["market_gate"]["pending_data"] >= supply_data["verdicts"]["total"]):
        alerts.append({"level": "high", "title": "市闸全部 pending",
                       "detail": "国际盘覆盖不足，今日不会产生 promoted/published"})
    elif supply_data["published"] == 0 and supply_data["verdicts"]["total"] > 0:
        alerts.append({"level": "low", "title": "今日无已发布判断",
                       "detail": "主链仍在复核，或数据不足；首页应显示“今天不硬推”"})
    fixtures = list(db.scalars(select(ApiFootballFixture)
                               .order_by(ApiFootballFixture.kickoff_utc.desc())
                               .limit(30)).all())
    return {
        "date": date,
        "env": get_settings().env,
        "sync": {"latest": sync_latest, "lag_seconds": sync_lag},
        "football_fixtures": [{
            "fixture_id": f.fixture_id, "kickoff_utc": f.kickoff_utc,
            "home": f.home_name, "away": f.away_name,
            "league": f.league_name, "status": f.status_short,
            "match_id": f.match_id or "", "link_method": f.link_method,
            "link_confidence": f.link_confidence,
        } for f in fixtures],
        "chain": chain,
        "football": football,
        "notifications": notif,
        "push_tokens": {
            "total": _count(db, PushToken),
            "enabled": _count(db, PushToken, PushToken.enabled.is_(True)),
        },
        "push_channel": _push_channel_status(),
        "interactions_24h": interaction_rows,
        "supply": supply_data,
        "recommendations": {"snapshots": snap_count, "plans": plan_count,
                            "review_failed": failed},
        "alerts": alerts,
    }
