"""会员权益、额度、市场权限。

支付/充值尚未接入；当前真实入口是管理后台手动开通。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (AnalysisQuota, AnalysisUsage, MarketAccess,
                      MembershipEvent, UserMembership, utcnow)

TIERS = ("free", "pro", "max")
DEFAULT_MARKETS = {
    "free": {"1x2"},
    "pro": {"1x2", "hhad", "score", "total_goals", "htft"},
    "max": {"1x2", "hhad", "score", "total_goals", "htft", "ou", "btts",
            "htft_detail", "correct_score", "corners"},
}


def tier_for(db: Session, user_id: str | None) -> str:
    if not user_id:
        return "free"
    now = utcnow()
    row = db.scalar(select(UserMembership).where(
        UserMembership.user_id == user_id,
        UserMembership.status == "active",
    ).order_by(UserMembership.expires_at.desc()).limit(1))
    if row is None:
        return "free"
    if row.expires_at <= now:
        row.status = "expired"
        db.add(MembershipEvent(
            user_id=user_id, action="expire", tier=row.tier,
            before_json={"status": "active"}, after_json={"status": "expired"},
            actor="system", note="到期自动失效",
        ))
        db.commit()
        return "free"
    return row.tier if row.tier in TIERS else "free"


def active_membership(db: Session, user_id: str | None) -> UserMembership | None:
    if not user_id:
        return None
    now = utcnow()
    row = db.scalar(select(UserMembership).where(
        UserMembership.user_id == user_id,
        UserMembership.status == "active",
    ).order_by(UserMembership.expires_at.desc()).limit(1))
    if row is not None and row.expires_at <= now:
        return None
    return row


def membership_payload(db: Session, user_id: str | None) -> dict:
    tier = tier_for(db, user_id)
    row = active_membership(db, user_id)
    return {
        "tier": tier,
        "status": row.status if row else "none",
        "expires_at": row.expires_at.isoformat() if row else None,
        "source": row.source if row else "",
        "is_paid": tier in ("pro", "max"),
    }


def expire_all(db: Session) -> int:
    """到期会员批量失效；seed/cron 调用。OPC：失败记 jobs + exception。"""
    from . import ops
    job_id = ops.job_start(db, "membership_expire")
    try:
        now = utcnow()
        rows = list(db.scalars(select(UserMembership).where(
            UserMembership.status == "active",
            UserMembership.expires_at <= now,
        )).all())
        for row in rows:
            row.status = "expired"
            db.add(MembershipEvent(
                user_id=row.user_id, action="expire", tier=row.tier,
                before_json={"status": "active", "expires_at": row.expires_at.isoformat()},
                after_json={"status": "expired"}, actor="system",
                note="到期自动失效",
            ))
        if rows:
            db.commit()
        ops.job_finish(db, job_id, "ok")
        return len(rows)
    except Exception as exc:
        db.rollback()
        ops.job_finish(db, job_id, "error", f"{type(exc).__name__}: {exc}")
        ops.exception(db, "membership_expire_error", str(exc), severity=3,
                      source="membership_expire", dedupe_key="membership_expire_error")
        return 0


def grant(db: Session, user_id: str, tier: str, days: int,
          actor: str = "admin", note: str = "") -> UserMembership:
    if tier not in ("pro", "max"):
        raise ValueError("tier 必须是 pro/max")
    days = max(1, min(int(days), 3650))
    now = utcnow()
    old = active_membership(db, user_id)
    if old is not None:
        old.status = "revoked"
        db.add(MembershipEvent(
            user_id=user_id, action="revoke", tier=old.tier,
            before_json={"status": "active", "expires_at": old.expires_at.isoformat()},
            after_json={"status": "revoked"}, actor=actor,
            note="手动开通前撤销旧会员",
        ))
        db.flush()
    row = UserMembership(
        user_id=user_id, tier=tier, status="active",
        starts_at=now, expires_at=now + timedelta(days=days),
        source="admin_manual", granted_by=actor, note=note[:200],
    )
    db.add(row)
    db.flush()
    db.add(MembershipEvent(
        user_id=user_id, action="grant", tier=tier,
        before_json=None,
        after_json={"tier": tier, "days": days,
                    "expires_at": row.expires_at.isoformat()},
        actor=actor, note=note[:200],
    ))
    db.commit()
    db.refresh(row)
    return row


def revoke(db: Session, user_id: str, actor: str = "admin",
           note: str = "") -> bool:
    row = active_membership(db, user_id)
    if row is None:
        return False
    row.status = "revoked"
    db.add(MembershipEvent(
        user_id=user_id, action="revoke", tier=row.tier,
        before_json={"status": "active", "expires_at": row.expires_at.isoformat()},
        after_json={"status": "revoked"}, actor=actor, note=note[:200],
    ))
    db.commit()
    return True


def quota_limit(tier: str) -> int | None:
    return 1 if tier == "free" else None


def quota_state(db: Session, user_id: str, trade_date: str, tier: str) -> dict:
    limit = quota_limit(tier)
    row = db.scalar(select(AnalysisQuota).where(
        AnalysisQuota.user_id == user_id,
        AnalysisQuota.trade_date == trade_date,
    ))
    used = row.used if row else 0
    return {"limit": limit, "used": used,
            "remaining": None if limit is None else max(0, limit - used)}


def can_analyze(db: Session, user_id: str, trade_date: str,
                match_id: str, tier: str) -> tuple[bool, str]:
    """只检查，不扣额度；生成成功后再 consume。"""
    if tier in ("pro", "max"):
        return True, ""
    limit = quota_limit(tier) or 1
    existing = db.scalar(select(AnalysisUsage).where(
        AnalysisUsage.user_id == user_id,
        AnalysisUsage.trade_date == trade_date,
        AnalysisUsage.match_id == match_id,
    ))
    if existing is not None:
        return True, ""
    row = db.scalar(select(AnalysisQuota).where(
        AnalysisQuota.user_id == user_id,
        AnalysisQuota.trade_date == trade_date,
    ))
    used = row.used if row else 0
    if used >= limit:
        return False, "今日免费分析已用完"
    return True, ""


def consume_analysis(db: Session, user_id: str, trade_date: str,
                     match_id: str, tier: str) -> tuple[bool, str]:
    """免费用户每天 1 场；同一场重复打开不重复扣。"""
    if tier in ("pro", "max"):
        return True, ""
    limit = quota_limit(tier) or 1
    existing = db.scalar(select(AnalysisUsage).where(
        AnalysisUsage.user_id == user_id,
        AnalysisUsage.trade_date == trade_date,
        AnalysisUsage.match_id == match_id,
    ))
    if existing is not None:
        return True, ""
    row = db.scalar(select(AnalysisQuota).where(
        AnalysisQuota.user_id == user_id,
        AnalysisQuota.trade_date == trade_date,
    ))
    if row is None:
        row = AnalysisQuota(user_id=user_id, trade_date=trade_date,
                            limit_count=limit, used=0)
        db.add(row)
        db.flush()
    if row.used >= limit:
        return False, "今日免费分析已用完"
    row.used += 1
    db.add(AnalysisUsage(user_id=user_id, trade_date=trade_date,
                         match_id=match_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return True, ""
    return True, ""


def market_allowed(db: Session, tier: str, market_key: str) -> bool:
    try:
        row = db.scalar(select(MarketAccess).where(
            MarketAccess.tier == tier,
            MarketAccess.market_key == market_key,
        ))
        if row is not None:
            return bool(row.enabled)
    except Exception:
        db.rollback()
    return market_key in DEFAULT_MARKETS.get(tier, set())


def seed_market_access(db: Session) -> None:
    """幂等种子：Pro 竞彩；Max 全市场但由数据接入决定实际展示。

    旧测试库/半迁移库可能缺表；种子失败不能阻塞应用启动。
    """
    try:
        for tier, keys in DEFAULT_MARKETS.items():
            for key in keys:
                row = db.scalar(select(MarketAccess).where(
                    MarketAccess.tier == tier,
                    MarketAccess.market_key == key,
                ))
                if row is None:
                    db.add(MarketAccess(tier=tier, market_key=key, enabled=True,
                                        note="v4 seed"))
        db.commit()
    except (IntegrityError, Exception):
        db.rollback()
