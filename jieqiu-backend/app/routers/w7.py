"""W7 端点：F20 分享（素材工厂+编号可验）、F18 市场配置、/me/export。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bet, Memory, ShareCard, User
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
    """导出用户全部数据（JSON；不含设备令牌——安全边界）。"""
    bets = db.scalars(select(Bet).where(Bet.user_id == user.id)).all()
    memories = db.scalars(select(Memory).where(Memory.user_id == user.id)).all()
    shares = db.scalars(select(ShareCard).where(ShareCard.user_id == user.id)).all()
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
            "created_at": user.created_at.isoformat(),
        },
        "bets": [{"verdict_id": b.verdict_id, "amount": b.amount,
                  "pick_dir": b.pick_dir, "created_at": b.created_at.isoformat()}
                 for b in bets],
        "memories": [{"key": m.key, "value": m.value, "source": m.source}
                     for m in memories],
        "shares": [{"share_id": c.share_id, "kind": c.kind} for c in shares],
        "note": "设备令牌不随导出（安全边界）。注销冷静期满后本数据将被清除。",
    }
