"""AI 助理 API：站内信 inbox、关注、通知设置、Android 推送 token。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (Notification, NotifySettings, PushToken, SPMatch,
                      User, WatchTarget)
from ..modules.users import user_from_token

router = APIRouter(tags=["assistant"])


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    u = user_from_token(db, authorization)
    if u is None:
        raise HTTPException(401, "未登录")
    return u


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WatchBody(BaseModel):
    target_type: str = "match"
    target_id: str
    events: list[str] | None = None


class NotifyBody(BaseModel):
    channels: list[str] | None = None
    event_types: list[str] | None = None
    quiet_start: str | None = None
    quiet_end: str | None = None
    daily_cap: int | None = None
    paused: bool | None = None


class PushRegister(BaseModel):
    platform: str = "android"
    provider: str = "jpush"
    token: str
    app_version: str = ""


class PushUnregister(BaseModel):
    token: str


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


@router.get("/me/inbox")
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


@router.get("/me/inbox/unread-count")
def inbox_unread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.channel == "inapp",
        Notification.opened_at.is_(None))) or 0
    return {"unread": n}


@router.post("/me/inbox/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id or n.channel != "inapp":
        raise HTTPException(404, "not found")
    if n.opened_at is None:
        n.opened_at = _now()
        db.commit()
    return {"ok": True}


@router.post("/me/inbox/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.channel == "inapp",
        Notification.opened_at.is_(None))).all()
    now = _now()
    for n in rows:
        n.opened_at = now
    db.commit()
    return {"ok": True, "count": len(rows)}


@router.post("/me/inbox/{notification_id}/click")
def click(notification_id: int, user: User = Depends(current_user),
          db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "not found")
    now = _now()
    n.opened_at = n.opened_at or now
    n.clicked_at = now
    db.commit()
    return {"ok": True, "deeplink": n.deeplink}


@router.get("/me/watch")
def watch_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(WatchTarget).where(WatchTarget.user_id == user.id)
                      .order_by(WatchTarget.id.desc())).all()
    return {"items": [{"id": w.id, "target_type": w.target_type,
                       "target_id": w.target_id, "events": w.events or []}
                      for w in rows]}


@router.post("/me/watch")
def watch_add(body: WatchBody, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    if body.target_type not in ("match", "team", "league"):
        raise HTTPException(422, "target_type 必须是 match/team/league")
    tid = body.target_id.strip()
    if not tid:
        raise HTTPException(422, "target_id 不能为空")
    if body.target_type == "match" and db.get(SPMatch, tid) is None:
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
    db.commit()
    db.refresh(row)
    return {"id": row.id, "target_type": row.target_type, "target_id": row.target_id,
            "events": row.events or []}


@router.delete("/me/watch/{watch_id}")
def watch_remove(watch_id: int, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    row = db.get(WatchTarget, watch_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/me/notify-settings")
def notify_get(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _notify_dict(db.get(NotifySettings, user.id))


@router.put("/me/notify-settings")
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
    db.commit()
    return _notify_dict(row)

@router.post("/push/register")
def push_register(body: PushRegister, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    if body.platform != "android":
        raise HTTPException(422, "MVP 只支持 Android 推送")
    if body.provider != "jpush":
        raise HTTPException(422, "MVP 只支持 JPush")
    token = body.token.strip()
    if not token:
        raise HTTPException(422, "token 不能为空")
    row = db.scalar(select(PushToken).where(
        PushToken.provider == body.provider, PushToken.token == token))
    if row is None:
        row = PushToken(user_id=user.id, platform=body.platform,
                        provider=body.provider, token=token,
                        app_version=body.app_version[:32])
        db.add(row)
    else:
        row.user_id = user.id
        row.platform = body.platform
        row.enabled = True
        row.failure_count = 0
        row.last_error = ""
        row.app_version = body.app_version[:32]
        row.last_seen = _now()
    db.commit()
    return {"ok": True, "id": row.id}


@router.post("/push/unregister")
def push_unregister(body: PushUnregister, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    row = db.scalar(select(PushToken).where(
        PushToken.user_id == user.id, PushToken.token == body.token))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True}
