"""合规状态：年龄门、未成年锁定、自排除。

原则：本机可以拦截，但服务端必须也是事实源；重装/换设备不能绕过。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ...models import User
from ...modules.users import today_cn

PERMANENT_UNTIL = datetime(2099, 12, 31, 23, 59, 59)
_CN = timezone(timedelta(hours=8))


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _active_until(user: User) -> datetime | None:
    until = user.self_exclusion_until
    if until is not None and until.tzinfo is not None:
        until = until.astimezone(timezone.utc).replace(tzinfo=None)
    return until


def is_excluded(user: User | None, now: datetime | None = None) -> bool:
    if user is None:
        return False
    until = _active_until(user)
    if until is None:
        return False
    return until > (now or _now_utc_naive())


def bet_block_reason(user: User | None, now: datetime | None = None) -> str | None:
    """下注/记注前的服务端硬门；返回 UI 可展示的原因码。"""
    if user is None:
        return "login_required"
    if user.under18_locked:
        return "under18"
    if is_excluded(user, now):
        return "self_excluded"
    if user.rested_until and user.rested_until >= today_cn():
        return "rested"
    return None


def state(user: User | None) -> dict:
    if user is None:
        return {
            "authenticated": False,
            "age_verified": False,
            "under18_locked": False,
            "self_exclusion": {"active": False, "until": None,
                               "permanent": False, "reason": ""},
            "can_bet": False,
            "block_reason": "login_required",
        }
    until = _active_until(user)
    excluded = is_excluded(user)
    return {
        "authenticated": True,
        "age_verified": bool(user.age_verified),
        "under18_locked": bool(user.under18_locked),
        "self_exclusion": {
            "active": excluded,
            "until": until.isoformat(timespec="seconds") if until else None,
            "permanent": bool(until and until >= PERMANENT_UNTIL),
            "reason": user.self_exclusion_reason or "",
        },
        "can_bet": bet_block_reason(user) is None,
        "block_reason": bet_block_reason(user),
    }


def verify_age(user: User, adult: bool, birth_year: int | None = None) -> dict:
    """自证成年：不强制收集出生日期；未成年立即锁定。"""
    user.age_verified = bool(adult)
    if birth_year is not None:
        current = datetime.now(_CN).year
        if birth_year < current - 120 or birth_year > current:
            raise ValueError("birth_year 不合法")
        user.birth_year = birth_year
        user.under18_locked = (current - birth_year) < 18
    else:
        user.under18_locked = not adult
    return state(user)


def set_under18_lock(user: User, locked: bool) -> dict:
    if not locked and not user.age_verified:
        raise ValueError("未完成年龄确认，不能解除未成年限制")
    user.under18_locked = bool(locked)
    return state(user)


def set_self_exclusion(user: User, days: int | None, permanent: bool,
                       reason: str = "") -> dict:
    if not permanent and (days is None or days < 1 or days > 3650):
        raise ValueError("自排除天数必须在 1–3650 天，或选择永久")
    until = PERMANENT_UNTIL if permanent else _now_utc_naive() + timedelta(days=int(days or 1))
    user.self_exclusion_at = _now_utc_naive()
    user.self_exclusion_until = until
    user.self_exclusion_reason = (reason or "")[:128]
    return state(user)


def set_assessment(user: User, score: int, answers: dict | None = None) -> dict:
    if score < 0 or score > 27:
        raise ValueError("PGSI 分数必须在 0–27")
    payload = dict(user.compliance_json or {})
    payload["pgsi"] = {
        "score": int(score),
        "answers": answers or {},
        "at": _now_utc_naive().isoformat(timespec="seconds"),
    }
    user.compliance_json = payload
    return state(user)
