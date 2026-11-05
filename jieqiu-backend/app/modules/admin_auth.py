"""新版管理后台认证与 RBAC。

- 首次启动用 `JQ_ADMIN_PASSWORD`（回退 `JQ_CONSOLE_PASSWORD`）创建 admin。
- 密码 PBKDF2-SHA256 存储，不依赖额外库。
- 会话只存进程内，HttpOnly cookie `admin_t`；单进程 OPC 足够。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AdminUser

ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}
SESSION_COOKIE = "admin_t"
SESSION_TTL = 86400
_LOGIN_WINDOW = 600
_LOGIN_MAX_FAILS = 5
_ITERATIONS = 210_000
_SESSIONS: dict[str, dict] = {}
_LOGIN_FAILS: dict[str, list[float]] = {}
_LOGIN_LOCK = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                     int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def login_locked(key: str) -> bool:
    now = time.time()
    with _LOGIN_LOCK:
        recent = [t for t in _LOGIN_FAILS.get(key, []) if now - t < _LOGIN_WINDOW]
        _LOGIN_FAILS[key] = recent
        return len(recent) >= _LOGIN_MAX_FAILS


def record_login_fail(key: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILS.setdefault(key, []).append(time.time())
        if len(_LOGIN_FAILS) > 5000:
            for stale in list(_LOGIN_FAILS)[:1000]:
                _LOGIN_FAILS.pop(stale, None)


def clear_login_fail(key: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILS.pop(key, None)


@dataclass(frozen=True)
class AdminPrincipal:
    id: int
    username: str
    role: str


def ensure_bootstrap_admin(db: Session) -> AdminUser | None:
    existing = db.scalar(select(func.count()).select_from(AdminUser))
    if existing:
        return None
    st = get_settings()
    password = st.admin_password or st.console_password
    if not password and st.env in ("dev", "test"):
        password = "dev"
    if not password:
        return None
    user = AdminUser(username="admin", password_hash=hash_password(password),
                     role="admin", enabled=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> AdminUser | None:
    ensure_bootstrap_admin(db)
    user = db.scalar(select(AdminUser).where(AdminUser.username == username.strip()))
    if user is None or not user.enabled:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = _utcnow()
    db.commit()
    return user


def create_session(user: AdminUser) -> tuple[str, int]:
    now = time.time()
    for token, info in list(_SESSIONS.items()):
        if info["exp"] < now:
            _SESSIONS.pop(token, None)
    if len(_SESSIONS) > 1000:
        for token in list(_SESSIONS)[:500]:
            _SESSIONS.pop(token, None)
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = {"exp": now + SESSION_TTL, "id": user.id,
                        "username": user.username, "role": user.role,
                        "csrf": secrets.token_urlsafe(24)}
    return token, SESSION_TTL


def revoke_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def revoke_all_for_user(user_id: int) -> int:
    """角色/启用/密码/删除变更后撤销该账号所有会话，避免旧 cookie 继续用旧权限。"""
    removed = 0
    for token, info in list(_SESSIONS.items()):
        if info.get("id") == user_id:
            _SESSIONS.pop(token, None)
            removed += 1
    return removed


def csrf_guard(request: Request) -> None:
    """后台写操作 CSRF：登录接口豁免，其余非安全方法必须带会话 CSRF。"""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.url.path == "/admin/api/login":
        return
    info = session_info(request)
    if info is None:
        return  # 认证依赖会返回 401，避免把未登录误报成 CSRF
    supplied = request.headers.get("x-csrf-token", "")
    expected = str(info.get("csrf", ""))
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(403, "CSRF 校验失败，请刷新后台后重试")


def session_info(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    info = _SESSIONS.get(token)
    if info is None:
        return None
    if info["exp"] < time.time():
        _SESSIONS.pop(token, None)
        return None
    return info


def optional_admin(request: Request) -> AdminPrincipal | None:
    info = session_info(request)
    if info is None:
        return None
    return AdminPrincipal(id=info["id"], username=info["username"], role=info["role"])


def current_admin(request: Request) -> AdminPrincipal:
    principal = optional_admin(request)
    if principal is None:
        raise HTTPException(401, "需要管理后台登录")
    return principal


def require_role(min_role: str):
    threshold = ROLE_LEVEL[min_role]

    def dependency(principal: AdminPrincipal = Depends(current_admin)) -> AdminPrincipal:
        if ROLE_LEVEL.get(principal.role, 0) < threshold:
            raise HTTPException(403, "权限不足")
        return principal

    return dependency


def list_users(db: Session) -> list[AdminUser]:
    ensure_bootstrap_admin(db)
    return list(db.scalars(select(AdminUser).order_by(AdminUser.id)).all())


def create_user(db: Session, username: str, password: str, role: str = "operator") -> AdminUser:
    username = username.strip()
    if not username or len(username) > 64:
        raise ValueError("用户名不能为空且不超过 64 字符")
    if role not in ROLE_LEVEL:
        raise ValueError("角色必须是 viewer/operator/admin")
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    if db.scalar(select(AdminUser).where(AdminUser.username == username)):
        raise ValueError("用户名已存在")
    user = AdminUser(username=username, password_hash=hash_password(password),
                     role=role, enabled=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
