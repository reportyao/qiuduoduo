"""W5 认证核心（方案 B）：手机号/邮箱验证码 + 微信/Google/Apple OAuth + JWT。

安全设计：
- access JWT 15min（HS256，JQ_JWT_SECRET；生产未配置 → fail-closed）
- refresh 不透明随机串 30d，哈希入库；轮换；**复用检测 → 撤销整个 family**
- 验证码 6 位，HMAC 存储，5min TTL，5 次尝试，单次消费；同目标 60s/条 + 10 条/日
- 第三方 id_token 生产走 JWKS 验签（Google/Apple）；stub 仅非生产可用
- 不泄露账号是否存在（send 恒 200；verify 统一 401）
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AuthIdentity, RefreshToken, User, VerificationCode

def _now() -> datetime:
    """naive UTC（SQLite 往返剥 tz，比较必须同形）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# 进程内发送限流（OPC 单实例；多实例换 Redis）
_last_send: dict[str, float] = {}
_daily_count: dict[str, int] = {}
_daily_key: str = ""
_ip_sends: dict[str, list[float]] = {}   # 单 IP 每小时上限（防短信轰炸）
_IP_HOURLY_LIMIT = 20


# ---------------- JWT / refresh ----------------

def _secret() -> str:
    s = get_settings().jwt_secret
    if s:
        return s
    if get_settings().env == "prod":
        raise RuntimeError("JQ_JWT_SECRET 未配置：生产环境拒绝签发令牌")
    return "dev-only-secret"


def issue_access(user: User) -> tuple[str, int]:
    st = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=st.jwt_access_minutes)
    token = pyjwt.encode(
        {"sub": user.id, "typ": "access", "iat": int(time.time()), "exp": int(exp.timestamp())},
        _secret(), algorithm="HS256")
    return token, st.jwt_access_minutes * 60


def verify_access(token: str) -> str | None:
    try:
        payload = pyjwt.decode(token, _secret(), algorithms=["HS256"])
    except Exception:
        return None
    if payload.get("typ") != "access":
        return None
    return payload.get("sub")


def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh(db: Session, user: User, family_id: str | None = None) -> str:
    st = get_settings()
    raw = secrets.token_urlsafe(32)
    db.add(RefreshToken(
        user_id=user.id, token_hash=_hash_refresh(raw),
        family_id=family_id or secrets.token_hex(12),
        expires_at=_now() + timedelta(days=st.refresh_days)))
    db.commit()
    return raw


def rotate_refresh(db: Session, raw: str) -> dict | None:
    """轮换刷新令牌。复用已撤销令牌 → 撤销整个 family（盗用应对）。

    原子化：UPDATE ... WHERE revoked=0 抢占；rowcount=0 视为并发复用。
    """
    from sqlalchemy import update as _update
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash_refresh(raw)))
    if row is None:
        return None
    if row.revoked:
        _revoke_family(db, row.family_id)  # 复用检测：整个 family 视为已泄露
        return None
    if row.expires_at < _now():
        return None
    user = db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        return None
    res = db.execute(_update(RefreshToken)
                     .where(RefreshToken.id == row.id, RefreshToken.revoked.is_(False))
                     .values(revoked=True))
    db.commit()
    if (res.rowcount or 0) == 0:
        _revoke_family(db, row.family_id)  # 并发下已被使用 → 视为复用
        return None
    access, ttl = issue_access(user)
    new_raw = issue_refresh(db, user, family_id=row.family_id)
    return {"access_token": access, "refresh_token": new_raw,
            "expires_in": ttl, "token_type": "bearer"}


def _revoke_family(db: Session, family_id: str) -> None:
    for r in db.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)):
        r.revoked = True
    db.commit()


def revoke_refresh(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash_refresh(raw)))
    if row:
        row.revoked = True
        db.commit()


def tokens_for(db: Session, user: User) -> dict:
    access, ttl = issue_access(user)
    refresh = issue_refresh(db, user)
    return {"access_token": access, "refresh_token": refresh,
            "expires_in": ttl, "token_type": "bearer"}


# ---------------- 验证码 ----------------

def _target_hash(channel: str, target: str) -> str:
    return hmac.new(_secret().encode(), f"{channel}:{target}".encode(), hashlib.sha256).hexdigest()


def _code_hash(channel: str, target: str, purpose: str, code: str) -> str:
    raw = f"{channel}:{target}:{purpose}:{code}"
    return hmac.new(_secret().encode(), raw.encode(), hashlib.sha256).hexdigest()


def _daily_ok(target: str) -> bool:
    global _daily_key
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _daily_key != today:
        _daily_key = today
        _daily_count.clear()
    return _daily_count.get(target, 0) < get_settings().code_daily_limit


def _ip_ok(ip: str | None) -> bool:
    if not ip:
        return True
    now = time.time()
    arr = [t for t in _ip_sends.get(ip, []) if now - t < 3600]
    _ip_sends[ip] = arr
    return len(arr) < _IP_HOURLY_LIMIT


def send_code(db: Session, channel: str, target: str, purpose: str = "login",
              ip: str | None = None) -> dict:
    """生成并发送验证码。限流：同目标 60s / 10 条每日；同 IP 20 条/小时。"""
    st = get_settings()
    key = f"{channel}:{target}"
    now = time.time()
    if now - _last_send.get(key, 0) < st.code_send_interval_seconds:
        return {"ok": False, "retry_after": int(st.code_send_interval_seconds - (now - _last_send.get(key, 0)))}
    if not _daily_ok(key):
        return {"ok": False, "retry_after": 3600}
    if not _ip_ok(ip):
        return {"ok": False, "retry_after": 3600, "reason": "ip_limit"}
    code = f"{secrets.randbelow(1000000):06d}"
    db.add(VerificationCode(
        channel=channel, target_hash=_target_hash(channel, target),
        code_hash=_code_hash(channel, target, purpose, code), purpose=purpose,
        expires_at=_now() + timedelta(seconds=st.code_ttl_seconds)))
    db.commit()
    _last_send[key] = now
    _daily_count[key] = _daily_count.get(key, 0) + 1
    if ip:
        _ip_sends.setdefault(ip, []).append(now)
    _dispatch(channel, target, code)
    out = {"ok": True, "ttl": st.code_ttl_seconds}
    if st.env != "prod" and st.auth_stub:
        out["dev_code"] = code  # 仅非生产回显，便于联调
    return out


def _dispatch(channel: str, target: str, code: str) -> None:
    """真实通道：SMS=腾讯云短信 / Email=Resend；未配置时生产直接抛错（fail loud）。"""
    st = get_settings()
    if st.env == "prod" and st.auth_stub:
        raise RuntimeError("生产环境禁止 auth_stub：请配置真实短信/邮件通道")
    if channel == "sms":
        if st.sms_provider == "tencent" and st.wechat_app_secret:
            # 腾讯云短信 SDK 接入位（需 SecretId/Key/SdkAppId/模板；按官方 SDK 补齐）
            raise RuntimeError("腾讯云短信配置不完整（v1.5 接入）")
        return  # stub：不发真实短信
    if channel == "email":
        return  # stub：不发真实邮件


def verify_code(db: Session, channel: str, target: str, code: str, purpose: str = "login") -> bool:
    th = _target_hash(channel, target)
    row = db.scalar(
        select(VerificationCode)
        .where(VerificationCode.channel == channel, VerificationCode.target_hash == th,
               VerificationCode.purpose == purpose, VerificationCode.consumed.is_(False))
        .order_by(VerificationCode.id.desc()).limit(1))
    if row is None:
        return False
    if row.expires_at < _now():
        return False
    st = get_settings()
    row.attempts += 1
    if row.attempts > st.code_max_attempts:
        db.commit()
        return False
    ok = hmac.compare_digest(row.code_hash, _code_hash(channel, target, purpose, code))
    if ok:
        row.consumed = True
    db.commit()
    return ok


# ---------------- 第三方 OAuth ----------------

_WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"


def wechat_exchange(code: str) -> dict | None:
    """微信 code → {openid, unionid?}。stub：任意 code → 稳定假 openid。"""
    st = get_settings()
    if st.env != "prod" and st.auth_stub:
        openid = "wx_" + hashlib.sha256(code.encode()).hexdigest()[:20]
        return {"openid": openid}
    if not (st.wechat_app_id and st.wechat_app_secret):
        return None
    url = (f"{_WECHAT_TOKEN_URL}?appid={st.wechat_app_id}&secret={st.wechat_app_secret}"
           f"&code={code}&grant_type=authorization_code")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return None
    if "openid" not in data:
        return None
    return {"openid": data["openid"], "unionid": data.get("unionid")}


_JWKS_CACHE: dict[str, tuple[float, list]] = {}
_JWKS_URLS = {
    "google": "https://www.googleapis.com/oauth2/v3/certs",
    "apple": "https://appleid.apple.com/auth/keys",
}


def _jwks(provider: str) -> list:
    now = time.time()
    cached = _JWKS_CACHE.get(provider)
    if cached and now - cached[0] < 3600:
        return cached[1]
    with urllib.request.urlopen(_JWKS_URLS[provider], timeout=10) as r:
        keys = json.loads(r.read().decode()).get("keys", [])
    _JWKS_CACHE[provider] = (now, keys)
    return keys


def verify_oauth(provider: str, id_token: str) -> dict | None:
    """校验 Google/Apple id_token。返回 {sub, email, email_verified} 或 None。

    stub（仅非生产）：id_token = "stub:google:<sub>:<email>"
    """
    st = get_settings()
    if st.env != "prod" and st.auth_stub and id_token.startswith("stub:"):
        parts = id_token.split(":")
        if len(parts) < 4 or parts[1] != provider:
            return None
        return {"sub": parts[2], "email": parts[3] or None,
                "email_verified": bool(parts[3])}
    try:
        header = pyjwt.get_unverified_header(id_token)
        kid = header.get("kid")
        keys = _jwks(provider)
        key = next((k for k in keys if k.get("kid") == kid), None)
        if key is None:
            return None
        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        aud = st.google_client_id if provider == "google" else st.apple_client_id
        payload = pyjwt.decode(id_token, public_key, algorithms=["RS256"],
                               audience=aud or None, options={"verify_aud": bool(aud)})
        return {"sub": payload.get("sub"), "email": payload.get("email"),
                "email_verified": bool(payload.get("email_verified", payload.get("email")))}
    except Exception:
        return None


# ---------------- 用户与身份 ----------------

def mask_phone(p: str) -> str:
    return p[:3] + "****" + p[-4:] if len(p) == 11 else p


def mask_email(e: str) -> str:
    name, _, domain = e.partition("@")
    return (name[:1] + "***@" + domain) if domain else "***"


def find_user_by_identity(db: Session, provider: str, uid: str) -> User | None:
    ident = db.scalar(select(AuthIdentity).where(
        AuthIdentity.provider == provider, AuthIdentity.provider_uid == uid))
    return db.get(User, ident.user_id) if ident else None


def link_identity(db: Session, user: User, provider: str, uid: str, masked: str = "") -> None:
    existing = db.scalar(select(AuthIdentity).where(
        AuthIdentity.provider == provider, AuthIdentity.provider_uid == uid))
    if existing:
        if existing.user_id != user.id:
            raise ValueError("该第三方账号已绑定其他用户")
        return
    db.add(AuthIdentity(user_id=user.id, provider=provider, provider_uid=uid,
                        identifier_masked=masked))
    db.commit()


def create_user(db: Session, region: str, phone: str | None = None,
                email: str | None = None) -> User:
    import uuid as _uuid
    u = User(id=_uuid.uuid4().hex, device_token=_uuid.uuid4().hex, region=region)
    if phone:
        u.phone = phone
        u.phone_verified = True
        u.locale = "zh"
    if email:
        u.email = email
        u.email_verified = True
        u.locale = "en"
    db.add(u)
    db.commit()
    return u


def get_or_create_by_phone(db: Session, phone: str) -> tuple[User, bool]:
    u = db.scalar(select(User).where(User.phone == phone))
    if u:
        changed = False
        if not u.phone_verified:
            u.phone_verified = True
            changed = True
        if u.deleted_at is not None:
            u.deleted_at = None  # 登录 = 撤回注销（与设备登录同语义）
            changed = True
        if changed:
            db.commit()
        return u, False
    u = create_user(db, "cn", phone=phone)
    link_identity(db, u, "phone", phone, mask_phone(phone))
    return u, True


def get_or_create_by_email(db: Session, email: str) -> tuple[User, bool]:
    email = email.lower()
    u = db.scalar(select(User).where(User.email == email))
    if u:
        changed = False
        if not u.email_verified:
            u.email_verified = True
            changed = True
        if u.deleted_at is not None:
            u.deleted_at = None
            changed = True
        if changed:
            db.commit()
        return u, False
    u = create_user(db, "global", email=email)
    link_identity(db, u, "email", email, mask_email(email))
    return u, True


def public_user(u: User) -> dict:
    return {
        "user_id": u.id,
        "region": u.region,
        "persona": u.persona,
        "display_name": u.display_name,
        "phone": mask_phone(u.phone) if u.phone else None,
        "email": mask_email(u.email) if u.email else None,
        "phone_verified": u.phone_verified,
        "email_verified": u.email_verified,
    }
