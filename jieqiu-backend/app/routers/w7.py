"""W7 端点：F20 分享（素材工厂+编号可验）、F18 市场配置、/me/export。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (AuthIdentity, Bet, Memory, Notification, NotifySettings,
                      PushToken, ShareCard, User, UserEvent, WatchTarget)
from ..modules import users as U
from ..modules.share import (market_profile, share_streak, share_verdict,
                             share_weekly, verify_share)

router = APIRouter()


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> User:
    u = U.user_from_token(db, authorization)
    if u is None:
        raise HTTPException(401, "需要登录")
    if U.is_deleted(u):
        raise HTTPException(410, detail={
            "error": "account_deleted", "cooldown_days": 7,
            "message": "账号已注销（冷静期内）。同设备令牌登录即自动撤回。"})
    return u


# ---------- F20 分享 ----------

@router.post("/share/verdict/{verdict_id}")
def share_verdict_route(verdict_id: str, persona: str = "zhuanjia",
                        db: Session = Depends(get_db)):
    """判决分享卡（公开）：编号 = content_hash 前 12 位，可验。"""
    card, err = share_verdict(db, verdict_id, persona)
    if card is None:
        raise HTTPException(404, err)
    return {"share_id": card.share_id, "text": card.text,
            "url": f"/share/{card.share_id}",
            "deep_link": f"jieqiu://share/{card.share_id}"}


@router.post("/share/weekly")
def share_weekly_route(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """周报分享卡（需登录：含个人 P&L）。"""
    card, _ = share_weekly(db, user)
    return {"share_id": card.share_id, "text": card.text,
            "url": f"/share/{card.share_id}",
            "deep_link": f"jieqiu://share/{card.share_id}"}


@router.post("/share/streak")
def share_streak_route(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """连败/保护状态分享卡（需登录）。"""
    card, _ = share_streak(db, user)
    return {"share_id": card.share_id, "text": card.text,
            "url": f"/share/{card.share_id}",
            "deep_link": f"jieqiu://share/{card.share_id}"}


class ShareCardBody(BaseModel):
    kind: str
    verdict_id: str | None = None
    persona: str = "zhuanjia"


class ShareCardResponse(BaseModel):
    share_id: str
    kind: str | None = None
    text: str
    url: str
    deep_link: str


@router.post("/share/card", response_model=ShareCardResponse)
def share_card(body: ShareCardBody, authorization: str | None = Header(default=None),
               db: Session = Depends(get_db)):
    """兼容 TechSpec 的统一分享入口；按 kind 分发到三种素材。"""
    if body.kind == "verdict":
        if not body.verdict_id:
            raise HTTPException(422, "verdict_id 必填")
        card, err = share_verdict(db, body.verdict_id, body.persona)
    elif body.kind in ("weekly", "streak"):
        u = U.user_from_token(db, authorization)
        if u is None:
            raise HTTPException(401, "需要登录")
        if U.is_deleted(u):
            raise HTTPException(410, "账号处于注销冷静期")
        card, err = (share_weekly(db, u) if body.kind == "weekly" else share_streak(db, u))
    else:
        raise HTTPException(422, "kind 必须是 verdict / weekly / streak")
    if card is None:
        raise HTTPException(404, err or "share source not found")
    return {"share_id": card.share_id, "kind": card.kind, "text": card.text,
            "url": f"/share/{card.share_id}",
            "deep_link": f"jieqiu://share/{card.share_id}"}


@router.get("/share/{share_id}")
def share_get(share_id: str, db: Session = Depends(get_db)):
    """公开验卡：任何人独立复算 content_hash —— 篡改即暴露（F20 gate）。"""
    card = db.get(ShareCard, share_id)
    if card is None:
        raise HTTPException(404, "share not found")
    return verify_share(card)


@router.get("/shares/mine")
def shares_mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ShareCard).where(ShareCard.user_id == user.id)
        .order_by(ShareCard.created_at.desc()).limit(50)
    ).all()
    return [{"share_id": c.share_id, "kind": c.kind, "text": c.text,
             "created_at": c.created_at.isoformat()} for c in rows]


# ---------- F18 市场配置 ----------

@router.get("/me/market-profile")
def me_market(user: User = Depends(current_user)):
    return market_profile(user)


# ---------- 数据导出 ----------

@router.get("/me/export")
def me_export(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """导出用户全部数据（JSON；设备/推送令牌不导出）。"""
    bets = db.scalars(select(Bet).where(Bet.user_id == user.id)
                      .order_by(Bet.created_at)).all()
    memories = db.scalars(select(Memory).where(Memory.user_id == user.id)).all()
    shares = db.scalars(select(ShareCard).where(ShareCard.user_id == user.id)).all()
    watches = db.scalars(select(WatchTarget).where(WatchTarget.user_id == user.id)).all()
    notes = db.scalars(select(Notification).where(Notification.user_id == user.id)
                       .order_by(Notification.id.desc()).limit(1000)).all()
    settings = db.get(NotifySettings, user.id)
    tokens = db.scalars(select(PushToken).where(PushToken.user_id == user.id)).all()
    events = db.scalars(select(UserEvent).where(UserEvent.user_id == user.id)
                        .order_by(UserEvent.id.desc()).limit(1000)).all()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "user_id": user.id,
            "display_name": user.display_name,
            "persona": user.persona,
            "region": user.region,
            "locale": user.locale,
            "odds_format": user.odds_format,
            "discipline_on": user.discipline_on,
            "rested_until": user.rested_until,
            "phone": user.phone,          # 本人数据导出：完整号码
            "email": user.email,
            "phone_verified": bool(user.phone_verified),
            "email_verified": bool(user.email_verified),
            "created_at": user.created_at.isoformat(),
        },
        "auth_identities": [
            {"provider": i.provider, "identifier": i.provider_uid,
             "masked": i.identifier_masked,
             "created_at": i.created_at.isoformat()}
            for i in db.scalars(select(AuthIdentity).where(AuthIdentity.user_id == user.id))
        ],
        "bets": [{"verdict_id": b.verdict_id, "amount": b.amount, "sp": b.sp,
                  "pick_dir": b.pick_dir, "created_at": b.created_at.isoformat()}
                 for b in bets],
        "memories": [{"key": m.key, "value": m.value, "source": m.source,
                      "category": m.category, "confidence": m.confidence,
                      "expires_at": (m.expires_at.isoformat() if m.expires_at else None)}
                     for m in memories],
        "shares": [{"share_id": c.share_id, "kind": c.kind, "text": c.text,
                    "payload": c.payload, "created_at": c.created_at.isoformat()}
                   for c in shares],
        "watch_targets": [{"target_type": w.target_type, "target_id": w.target_id,
                           "events": w.events or [],
                           "created_at": w.created_at.isoformat()} for w in watches],
        "notifications": [{
            "id": n.id, "event_id": n.event_id, "channel": n.channel,
            "status": n.status, "title": n.title, "body": n.body,
            "deeplink": n.deeplink, "scheduled_at": n.scheduled_at.isoformat(),
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "opened_at": n.opened_at.isoformat() if n.opened_at else None,
            "clicked_at": n.clicked_at.isoformat() if n.clicked_at else None,
            "created_at": n.created_at.isoformat(),
        } for n in notes],
        "notify_settings": (None if settings is None else {
            "channels": settings.channels or [], "event_types": settings.event_types or [],
            "quiet_start": settings.quiet_start, "quiet_end": settings.quiet_end,
            "daily_cap": settings.daily_cap, "paused": bool(settings.paused),
        }),
        # 推送令牌本身是设备凭证，只导出元数据，不导出 token 原值。
        "push_tokens": [{"platform": t.platform, "provider": t.provider,
                         "enabled": bool(t.enabled), "app_version": t.app_version,
                         "failure_count": t.failure_count,
                         "last_seen": t.last_seen.isoformat() if t.last_seen else None}
                        for t in tokens],
        "user_events": [{"kind": e.kind, "target_id": e.target_id,
                         "metadata": e.metadata_json,
                         "created_at": e.created_at.isoformat()} for e in events],
        "note": ("设备令牌与推送 token 不随导出（安全边界）。"
                 "注销冷静期满后本数据将被清除。"),
    }
