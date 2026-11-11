"""AI 助理 API：站内信 inbox、关注、通知设置、Android 推送 token。"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import (Notification, NotifySettings, PushToken, SPMatch,
                      User, WatchTarget)
from ...modules.users import is_deleted, user_from_token

router = APIRouter(tags=["assistant"])


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    u = user_from_token(db, authorization)
    if u is None:
        raise HTTPException(401, "未登录")
    if is_deleted(u):
        raise HTTPException(410, detail={
            "error": "account_deleted", "cooldown_days": 7,
            "message": "账号处于注销冷静期，暂不可用。",
        })
    return u


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WatchBody(BaseModel):
    target_type: str = Field(default="match", max_length=8)
    target_id: str = Field(min_length=1, max_length=64)
    events: list[str] | None = None


class NotifyBody(BaseModel):
    channels: list[str] | None = None
    event_types: list[str] | None = None
    quiet_start: str | None = Field(default=None, max_length=5)
    quiet_end: str | None = Field(default=None, max_length=5)
    daily_cap: int | None = None
    paused: bool | None = None


class PushRegister(BaseModel):
    platform: str = Field(default="android", max_length=8)
    provider: str = Field(default="jpush", max_length=16)
    token: str = Field(min_length=1, max_length=256)
    app_version: str = Field(default="", max_length=32)


class PushUnregister(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class InboxItem(BaseModel):
    id: int
    event_id: int | None = None
    title: str
    body: str
    deeplink: str | None = None
    created_at: str
    opened_at: str | None = None
    clicked_at: str | None = None


class InboxResponse(BaseModel):
    unread: int
    items: list[InboxItem]


class UnreadResponse(BaseModel):
    unread: int


class OkResponse(BaseModel):
    ok: bool = True


class ReadAllResponse(OkResponse):
    count: int


class ClickResponse(OkResponse):
    deeplink: str | None = None


class WatchItem(BaseModel):
    id: int
    target_type: str
    target_id: str
    events: list[str]
    match_no: str | None = None
    home: str | None = None
    away: str | None = None
    league: str | None = None
    kickoff: str | None = None


class WatchListResponse(BaseModel):
    items: list[WatchItem]


class NotifyResponse(BaseModel):
    channels: list[str]
    event_types: list[str]
    quiet_start: str
    quiet_end: str
    daily_cap: int
    paused: bool


class PushRegisterResponse(OkResponse):
    id: int


class PushHealthResponse(BaseModel):
    configured: bool
    dryrun: bool
    provider: str
    enabled_tokens: int
    total_tokens: int
    last_error: str | None = None
    note: str


def _notify_dict(row: NotifySettings | None) -> dict:
    if row is None:
        return {"channels": ["inapp", "push"], "event_types": [],
                "quiet_start": "23:30", "quiet_end": "08:00",
                "daily_cap": 2, "paused": False}
    return {"channels": row.channels or ["inapp", "push"],
            "event_types": row.event_types or [],
            "quiet_start": row.quiet_start or "23:30",
            "quiet_end": row.quiet_end or "08:00",
            "daily_cap": int(row.daily_cap) if row.daily_cap is not None else 2,
            "paused": bool(row.paused)}


def _hm(v: str) -> bool:
    try:
        h, m = v.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


@router.get("/me/inbox", response_model=InboxResponse)
def inbox(unread: bool = False, limit: int = 30,
          user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    q = select(Notification).where(Notification.user_id == user.id,
                                   Notification.channel == "inapp")
    if unread:
        q = q.where(Notification.opened_at.is_(None))
    rows = db.scalars(q.order_by(Notification.id.desc()).limit(limit)).all()
    unread_n = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.channel == "inapp",
        Notification.opened_at.is_(None))) or 0
    return {"unread": unread_n, "items": [{
        "id": n.id, "event_id": n.event_id, "title": n.title, "body": n.body,
        "deeplink": n.deeplink, "created_at": str(n.created_at),
        "opened_at": str(n.opened_at) if n.opened_at else None,
        "clicked_at": str(n.clicked_at) if n.clicked_at else None,
    } for n in rows]}


@router.get("/me/inbox/unread-count", response_model=UnreadResponse)
def inbox_unread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.channel == "inapp",
        Notification.opened_at.is_(None))) or 0
    return {"unread": n}


@router.post("/me/inbox/{notification_id}/read", response_model=OkResponse)
def mark_read(notification_id: int = Path(..., ge=1, le=2**63 - 1),
              user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id or n.channel != "inapp":
        raise HTTPException(404, "not found")
    if n.opened_at is None:
        n.opened_at = _now()
        db.commit()
    return {"ok": True}


@router.post("/me/inbox/read-all", response_model=ReadAllResponse)
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.channel == "inapp",
        Notification.opened_at.is_(None))).all()
    now = _now()
    for n in rows:
        n.opened_at = now
    db.commit()
    return {"ok": True, "count": len(rows)}


@router.post("/me/inbox/{notification_id}/click", response_model=ClickResponse)
def click(notification_id: int = Path(..., ge=1, le=2**63 - 1),
          user: User = Depends(current_user),
          db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "not found")
    now = _now()
    n.opened_at = n.opened_at or now
    n.clicked_at = now
    db.commit()
    return {"ok": True, "deeplink": n.deeplink}


@router.get("/me/watch", response_model=WatchListResponse)
def watch_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(WatchTarget).where(WatchTarget.user_id == user.id)
                      .order_by(WatchTarget.id.desc())).all()
    match_ids = [w.target_id for w in rows if w.target_type == "match"]
    matches = {m.match_id: m for m in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(match_ids)))} if match_ids else {}
    items = []
    for w in rows:
        m = matches.get(w.target_id)
        items.append({
            "id": w.id, "target_type": w.target_type, "target_id": w.target_id,
            "events": w.events or [],
            "match_no": m.match_no if m else None,
            "home": m.home if m else None,
            "away": m.away if m else None,
            "league": m.league if m else None,
            "kickoff": m.kickoff if m else None,
        })
    return {"items": items}


@router.post("/me/watch", response_model=WatchItem)
def watch_add(body: WatchBody, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    if body.target_type != "match":
        raise HTTPException(422, "当前只支持关注比赛（team/league 事件源尚未接入）")
    tid = body.target_id.strip()
    if not tid:
        raise HTTPException(422, "target_id 不能为空")
    if db.get(SPMatch, tid) is None:
        raise HTTPException(404, "比赛不存在")
    row = db.scalar(select(WatchTarget).where(
        WatchTarget.user_id == user.id, WatchTarget.target_type == body.target_type,
        WatchTarget.target_id == tid))
    if row is None:
        row = WatchTarget(user_id=user.id, target_type=body.target_type,
                          target_id=tid, events=body.events or [])
        db.add(row)
    elif body.events is not None:
        row.events = body.events
    try:
        db.commit()
    except IntegrityError:
        # 双击/重试并发创建同一关注：回滚后返回已存在行。
        db.rollback()
        row = db.scalar(select(WatchTarget).where(
            WatchTarget.user_id == user.id, WatchTarget.target_type == body.target_type,
            WatchTarget.target_id == tid))
        if row is None:
            raise
    db.refresh(row)
    return {"id": row.id, "target_type": row.target_type, "target_id": row.target_id,
            "events": row.events or []}


@router.delete("/me/watch/{watch_id}", response_model=OkResponse)
def watch_remove(watch_id: int = Path(..., ge=1, le=2**63 - 1),
                 user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    row = db.get(WatchTarget, watch_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


class FollowBody(BaseModel):
    events: list[str] | None = None


def _watch_item(row: WatchTarget, match: SPMatch | None) -> dict:
    return {
        "id": row.id, "target_type": row.target_type, "target_id": row.target_id,
        "events": row.events or [],
        "match_no": match.match_no if match else None,
        "home": match.home if match else None,
        "away": match.away if match else None,
        "league": match.league if match else None,
        "kickoff": match.kickoff if match else None,
    }


@router.post("/matches/{match_id}/follow", response_model=WatchItem)
def follow_match(match_id: str, body: FollowBody | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    """F21 兼容接口：关注一场比赛（底层仍是 watch_targets）。"""
    m = db.get(SPMatch, match_id)
    if m is None:
        raise HTTPException(404, "比赛不存在")
    row = db.scalar(select(WatchTarget).where(
        WatchTarget.user_id == user.id, WatchTarget.target_type == "match",
        WatchTarget.target_id == match_id))
    if row is None:
        row = WatchTarget(user_id=user.id, target_type="match", target_id=match_id,
                          events=(body.events if body and body.events is not None else []))
        db.add(row)
    elif body is not None and body.events is not None:
        row.events = body.events
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(WatchTarget).where(
            WatchTarget.user_id == user.id, WatchTarget.target_type == "match",
            WatchTarget.target_id == match_id))
        if row is None:
            raise
    db.refresh(row)
    return _watch_item(row, m)


@router.delete("/matches/{match_id}/follow", response_model=OkResponse)
def unfollow_match(match_id: str, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    row = db.scalar(select(WatchTarget).where(
        WatchTarget.user_id == user.id, WatchTarget.target_type == "match",
        WatchTarget.target_id == match_id))
    if row is None:
        raise HTTPException(404, "not following")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/me/notify-settings", response_model=NotifyResponse)
def notify_get(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _notify_dict(db.get(NotifySettings, user.id))


@router.put("/me/notify-settings", response_model=NotifyResponse)
def notify_put(body: NotifyBody, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    row = db.get(NotifySettings, user.id)
    if row is None:
        row = NotifySettings(user_id=user.id)
        db.add(row)
    if body.channels is not None:
        ch = [c for c in body.channels if c in ("inapp", "push")]
        row.channels = ch or ["inapp"]
    if body.event_types is not None:
        row.event_types = body.event_types
    if body.quiet_start is not None:
        if not _hm(body.quiet_start):
            raise HTTPException(422, "quiet_start 格式 HH:MM")
        row.quiet_start = body.quiet_start
    if body.quiet_end is not None:
        if not _hm(body.quiet_end):
            raise HTTPException(422, "quiet_end 格式 HH:MM")
        row.quiet_end = body.quiet_end
    if body.daily_cap is not None:
        if not (0 <= body.daily_cap <= 10):
            raise HTTPException(422, "daily_cap 0-10")
        row.daily_cap = body.daily_cap
    if body.paused is not None:
        row.paused = body.paused
    try:
        db.commit()
    except IntegrityError:
        # 并发首次保存偏好：主键冲突后重试一次，此时行已存在。
        db.rollback()
        return notify_put(body, user, db)
    return _notify_dict(row)


@router.post("/push/register", response_model=PushRegisterResponse)
def push_register(body: PushRegister, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    if body.platform != "android":
        raise HTTPException(422, "MVP 只支持 Android 推送")
    if body.provider != "jpush":
        raise HTTPException(422, "MVP 只支持 JPush")
    token = body.token.strip()
    if not token:
        raise HTTPException(422, "token 不能为空")
    def attach(existing: PushToken) -> None:
        if existing.user_id != user.id:
            owner = db.get(User, existing.user_id)
            if owner is not None and not is_deleted(owner):
                raise HTTPException(409, "该推送令牌已绑定其他账号，请先解绑")
            # 原账号已注销时允许新设备接管，避免永久占用唯一令牌。
            existing.user_id = user.id
        existing.platform = body.platform
        existing.enabled = True
        existing.failure_count = 0
        existing.last_error = ""
        existing.app_version = body.app_version[:32]
        existing.last_seen = _now()

    row = db.scalar(select(PushToken).where(
        PushToken.provider == body.provider, PushToken.token == token))
    if row is None:
        row = PushToken(user_id=user.id, platform=body.platform,
                        provider=body.provider, token=token,
                        app_version=body.app_version[:32])
        db.add(row)
    else:
        attach(row)
    try:
        db.commit()
    except IntegrityError:
        # 双击/重试并发注册同一 token：回滚后接管已存在行，而不是 500。
        db.rollback()
        row = db.scalar(select(PushToken).where(
            PushToken.provider == body.provider, PushToken.token == token))
        if row is None:
            raise
        attach(row)
        db.commit()
    return {"ok": True, "id": row.id}


@router.post("/push/unregister", response_model=OkResponse)
def push_unregister(body: PushUnregister, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    row = db.scalar(select(PushToken).where(
        PushToken.user_id == user.id, PushToken.token == body.token))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True}


# ---------- 兼容别名（Feature-API-Mapping / TechSpec 旧路径） ----------

@router.get("/push/preferences", response_model=NotifyResponse)
def push_preferences_get(user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    return notify_get(user, db)


@router.put("/push/preferences", response_model=NotifyResponse)
def push_preferences_put(body: NotifyBody, user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    return notify_put(body, user, db)


@router.post("/push/preferences", response_model=NotifyResponse)
def push_preferences_post(body: NotifyBody, user: User = Depends(current_user),
                          db: Session = Depends(get_db)):
    """兼容 TechSpec 的 POST /push/preferences（与 PUT 同一实现）。"""
    return notify_put(body, user, db)


@router.get("/push/health", response_model=PushHealthResponse)
def push_health(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """推送通道健康：只报告本账号 token 与全局厂商配置，不泄漏 token。"""
    configured = bool(os.environ.get("JQ_JPUSH_APPKEY") and
                      os.environ.get("JQ_JPUSH_MASTER_SECRET"))
    dryrun = (os.environ.get("JQ_JPUSH_DRYRUN", "").strip() in ("1", "true", "yes")
              or not configured)
    total = db.scalar(select(func.count(PushToken.id)).where(
        PushToken.user_id == user.id)) or 0
    enabled = db.scalar(select(func.count(PushToken.id)).where(
        PushToken.user_id == user.id, PushToken.enabled.is_(True))) or 0
    last_error = db.scalar(select(PushToken.last_error).where(
        PushToken.user_id == user.id, PushToken.last_error != "")
        .order_by(PushToken.id.desc()).limit(1))
    return {
        "configured": configured, "dryrun": dryrun, "provider": "jpush",
        "enabled_tokens": enabled, "total_tokens": total,
        "last_error": last_error or None,
        "note": ("MVP 仅 Android/JPush；未配置厂商密钥时 worker 为 dry-run。"
                 "真实 token 由 Android 包注册。"),
    }
