"""事件扇出：关注/下注关系 → 站内信 + 推送队列。

规则：
- 站内信总是投递（除 paused）；推送受渠道/静默/日上限/Token 控制；
- 同 user+event+channel 唯一，worker 重跑不会重复；
- 推送文案中性，站内信可写队名/结论。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import (Bet, Event, Notification, NotifySettings, PushToken,
                      User, Verdict, WatchTarget)
from .render import render_notification

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))

DEFAULT_EVENTS = ["verdict_promoted", "verdict_change", "verdict_killed",
                  "close_soon", "final", "settled", "daily_brief"]


def _now_cn() -> datetime:
    return datetime.now(CN)


def _to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hm(value: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        h, m = value.split(":")
        return int(h), int(m)
    except Exception:
        return default


def _in_quiet(now: datetime, start: str, end: str) -> bool:
    sh, sm = _hm(start, (23, 30))
    eh, em = _hm(end, (8, 0))
    cur = now.hour * 60 + now.minute
    a, b = sh * 60 + sm, eh * 60 + em
    if a == b:
        return False
    if a < b:
        return a <= cur < b
    return cur >= a or cur < b


def _quiet_end_utc(now: datetime, end: str) -> datetime:
    eh, em = _hm(end, (8, 0))
    target = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return _to_utc_naive(target)


def _settings(db: Session, user_id: str) -> dict:
    row = db.get(NotifySettings, user_id)
    if row is None:
        return {"channels": ["inapp", "push"], "event_types": [],
                "quiet_start": "23:30", "quiet_end": "08:00",
                "daily_cap": 2, "paused": False}
    return {"channels": row.channels or ["inapp", "push"],
            "event_types": row.event_types or [],
            "quiet_start": row.quiet_start or "23:30",
            "quiet_end": row.quiet_end or "08:00",
            "daily_cap": int(row.daily_cap if row.daily_cap is not None else 2),
            "paused": bool(row.paused)}


def _has_token(db: Session, user_id: str) -> bool:
    return db.scalar(select(PushToken.id).where(
        PushToken.user_id == user_id, PushToken.enabled.is_(True)).limit(1)) is not None


def _get_notification(db: Session, user_id: str, event_id: int, channel: str):
    return db.scalar(select(Notification).where(
        Notification.user_id == user_id, Notification.event_id == event_id,
        Notification.channel == channel))


def _push_used_today(db: Session, user_id: str, now_cn: datetime) -> int:
    start_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = _to_utc_naive(start_cn)
    return db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user_id, Notification.channel == "push",
        Notification.created_at >= start_utc,
        Notification.status.in_(("pending", "sending", "sent")),
    )) or 0


def _recipients(db: Session, event: Event) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """返回 (用户集合, 下注用户集合, watch 事件白名单)。"""
    users: set[str] = set()
    bet_users: set[str] = set()
    watch_filter: dict[str, set[str]] = {}
    if event.type == "daily_brief":
        rows = db.scalars(select(User.id).where(User.deleted_at.is_(None)).limit(5000)).all()
        return set(rows), set(), {}
    if not event.match_id:
        return set(), set(), {}
    watches = db.scalars(select(WatchTarget).where(
        WatchTarget.target_type == "match", WatchTarget.target_id == event.match_id)).all()
    for w in watches:
        users.add(w.user_id)
        if w.events:
            watch_filter[w.user_id] = set(w.events)
    bet_users = set(db.scalars(
        select(Bet.user_id).join(Verdict, Bet.verdict_id == Verdict.id)
        .where(Verdict.match_id == event.match_id)).all())
    users |= bet_users
    return users, bet_users, watch_filter


def fanout_events(db: Session, limit: int = 100, now_cn: datetime | None = None) -> dict:
    now_cn = now_cn or _now_cn()
    now_utc = _to_utc_naive(now_cn)
    events = db.scalars(select(Event).where(
        Event.fanout_at.is_(None),
    ).order_by(Event.id).limit(limit)).all()
    inapp_n = push_n = suppressed = 0
    for event in events:
        if event.expires_at is not None and str(event.expires_at) < str(now_utc):
            event.fanout_at = now_utc
            db.commit()
            continue
        users, bet_users, watch_filter = _recipients(db, event)
        for uid in users:
            cfg = _settings(db, uid)
            if cfg["paused"]:
                continue
            if cfg["event_types"] and event.type not in cfg["event_types"]:
                continue
            allowed = watch_filter.get(uid)
            if allowed and event.type not in allowed and uid not in bet_users:
                continue
            inapp = render_notification(event, "inapp")
            title, body, link = (inapp["title"][:128], inapp["body"][:512],
                                 inapp["deeplink"][:256])
            if _get_notification(db, uid, event.id, "inapp") is None:
                db.add(Notification(
                    user_id=uid, event_id=event.id, channel="inapp", status="sent",
                    title=title, body=body, deeplink=link,
                    scheduled_at=now_utc, sent_at=now_utc))
                inapp_n += 1
            if "push" not in cfg["channels"]:
                continue
            if not _has_token(db, uid):
                if _get_notification(db, uid, event.id, "push") is None:
                    db.add(Notification(
                        user_id=uid, event_id=event.id, channel="push", status="suppressed",
                        title="", body="", deeplink="", scheduled_at=now_utc,
                        last_error="no_token"))
                    suppressed += 1
                continue
            if cfg["daily_cap"] <= 0:
                if _get_notification(db, uid, event.id, "push") is None:
                    db.add(Notification(
                        user_id=uid, event_id=event.id, channel="push", status="suppressed",
                        title="", body="", deeplink="", scheduled_at=now_utc,
                        last_error="daily_cap"))
                    suppressed += 1
                continue
            p = render_notification(event, "push")
            p = {"title": p["title"][:128], "body": p["body"][:512],
                 "deeplink": p["deeplink"][:256]}
            status, sched, err = "pending", now_utc, ""
            if _in_quiet(now_cn, cfg["quiet_start"], cfg["quiet_end"]):
                if event.type == "close_soon":
                    status, err = "suppressed", "quiet_hours"
                else:
                    sched = _quiet_end_utc(now_cn, cfg["quiet_end"])
            if _push_used_today(db, uid, now_cn) >= cfg["daily_cap"]:
                status, err = "suppressed", "daily_cap"
            if _get_notification(db, uid, event.id, "push") is None:
                db.add(Notification(
                    user_id=uid, event_id=event.id, channel="push", status=status,
                    title=p["title"], body=p["body"], deeplink=p["deeplink"],
                    scheduled_at=sched, last_error=err))
                if status == "pending":
                    push_n += 1
                else:
                    suppressed += 1
        event.fanout_at = now_utc
        db.commit()
    return {"events": len(events), "inapp": inapp_n, "push": push_n,
            "suppressed": suppressed}
