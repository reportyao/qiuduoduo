"""W6 用户域：设备令牌认证、连败保护（F11）、休息（F7）、记忆（F13）。

纯函数 + 数据访问分离：streak 的判定逻辑是纯函数，可 100% 回放（gate）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Bet, Memory, User, Verdict

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


def today_cn() -> str:
    return datetime.now(CN).strftime("%Y-%m-%d")


# ---------- 认证（设备令牌=免登录态；W5 增补手机号/邮箱绑定 + JWT） ----------

def login_device(db: Session, token: str | None) -> tuple[User, bool]:
    """令牌存在则登录（注销冷静期内同令牌登录 = 撤回注销），否则创建。返回 (user, created)。"""
    if token:
        u = db.scalar(select(User).where(User.device_token == token))
        if u:
            if u.deleted_at is not None:
                u.deleted_at = None  # 冷静期内撤回注销
                db.commit()
            return u, False
    token = token or uuid.uuid4().hex
    u = User(id=uuid.uuid4().hex, device_token=token)
    db.add(u)
    db.commit()
    return u, True


def soft_delete(db: Session, user: User) -> None:
    """注销（7 天冷静期）：打标不删数据；同令牌登录即撤回。"""
    user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def is_deleted(user: User) -> bool:
    return user.deleted_at is not None


def purge_expired_deletions(db: Session, days: int = 7) -> dict:
    """注销期满清除：删除超过冷静期的用户及其全部数据（含认证标识与令牌）。

    返回 {purged_users, removed_bets, removed_memories, removed_shares,
          removed_identities, removed_tokens}。
    由每日 cron 调用（python -m app.purge_cli）。
    """
    from ..models import (AuthIdentity as AI, Bet as B, Memory as M,
                          Notification as N, NotifySettings as NS,
                          PushToken as PT, RefreshToken as RT, ShareCard as S,
                          UserEvent as UE, WatchTarget as WT)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    expired = db.scalars(
        select(User).where(User.deleted_at.isnot(None), User.deleted_at <= cutoff)
    ).all()
    counts = {"purged_users": 0, "removed_bets": 0, "removed_memories": 0,
              "removed_shares": 0, "removed_identities": 0, "removed_tokens": 0,
              "removed_notifications": 0, "removed_watches": 0,
              "removed_push_tokens": 0, "removed_user_events": 0,
              "removed_notify_settings": 0}
    for u in expired:
        for table, key in ((B, "removed_bets"), (M, "removed_memories"),
                           (S, "removed_shares"), (AI, "removed_identities"),
                           (RT, "removed_tokens"), (N, "removed_notifications"),
                           (WT, "removed_watches"), (PT, "removed_push_tokens"),
                           (UE, "removed_user_events"), (NS, "removed_notify_settings")):
            rows = db.scalars(select(table).where(table.user_id == u.id)).all()
            for row in rows:
                db.delete(row)
            counts[key] += len(rows)
        db.delete(u)
        counts["purged_users"] += 1
    db.commit()
    return counts


def user_from_token(db: Session, authorization: str | None) -> User | None:
    """Bearer 兼容两种：W5 JWT access token（优先）与旧设备令牌（免登录态）。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    from .auth import verify_access
    uid = verify_access(token)
    if uid:
        return db.get(User, uid)
    return db.scalar(select(User).where(User.device_token == token))


# ---------- F11 连败保护（纯函数可回放） ----------

def replay_streak(results: list[str], threshold: int = 3) -> dict:
    """从结算序列（按时间序，'win'/'lose'）计算连败与是否触发保护。

    纯函数 —— 触发准确率 100%（回放）的 gate 由此保证。
    连败 = 结尾起连续 lose 的长度；win 清零。
    """
    streak = 0
    for r in reversed(results):
        if r == "lose":
            streak += 1
        else:
            break
    return {"streak": streak, "triggered": streak >= threshold, "threshold": threshold}


def bet_pnl(bet: Bet, verdict: Verdict) -> float | None:
    """按注单赔率快照计算真实盈亏：赢 = 本金×(SP−1)，输 = −本金。"""
    if not verdict.settled:
        return None
    if verdict.settled == "lose":
        return round(-bet.amount, 2)
    sp = bet.sp or (verdict.pick or {}).get("sp")
    if isinstance(sp, (int, float)) and sp > 1:
        return round(bet.amount * (float(sp) - 1), 2)
    # 旧注单没有赔率快照：不能把赢单算成 +100% 利润（会高估 P&L）；返回未知。
    return None


def user_streak(db: Session, user: User) -> dict:
    """用户当前连败（基于其已结算注单，按判决开赛时间排序）。"""
    rows = db.execute(
        select(Bet, Verdict)
        .join(Verdict, Bet.verdict_id == Verdict.id)
        .where(Bet.user_id == user.id, Verdict.settled.isnot(None))
        .order_by(Verdict.kickoff)
    ).all()
    results = [v.settled for _, v in rows]
    rep = replay_streak(results)
    active = bool(user.discipline_on and rep["triggered"])
    pnl = sum((bet_pnl(b, v) or 0) for b, v in rows)
    return rep | {"active": active, "discipline_on": user.discipline_on,
                  "settled_bets": len(rows), "pnl": round(pnl, 2),
                  "rested": bool(user.rested_until and user.rested_until >= today_cn()),
                  "rested_until": user.rested_until}


# ---------- F7 休息 ----------

def set_rest(db: Session, user: User, days: int = 1) -> str:
    until = (datetime.now(CN) + timedelta(days=days)).strftime("%Y-%m-%d")
    user.rested_until = until
    db.commit()
    return until


def clear_rest(db: Session, user: User) -> None:
    user.rested_until = ""
    db.commit()


# ---------- F13 记忆（冲突必问不静默覆盖） ----------

def upsert_memory(db: Session, user_id: str, key: str, value: str,
                  source: str = "你说过", confirm: bool = False) -> tuple[Memory | None, str]:
    """返回 (memory, status)。status: created / updated / conflict。

    冲突（已有不同值）且未 confirm → 不覆盖，返回 (None, "conflict")。
    """
    key = key.strip()[:64].replace("/", "-")  # 防止 "/" 破坏 DELETE /me/memories/{key} 路由
    value = value.strip()[:256]
    if not key:
        raise ValueError("memory key 不能为空")
    m = db.scalar(select(Memory).where(Memory.user_id == user_id, Memory.key == key))
    if m is None:
        m = Memory(user_id=user_id, key=key, value=value, source=source)
        db.add(m)
        db.commit()
        return m, "created"
    if m.value != value and not confirm:
        return None, "conflict"
    m.value = value
    m.source = source
    db.commit()
    return m, "updated"


def list_memories(db: Session, user_id: str) -> list[Memory]:
    return db.scalars(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
    ).all()


def delete_memory(db: Session, user_id: str, key: str) -> bool:
    m = db.scalar(select(Memory).where(Memory.user_id == user_id, Memory.key == key))
    if m is None:
        return False
    db.delete(m)
    db.commit()
    return True
