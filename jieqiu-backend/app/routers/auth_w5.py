"""W5 认证端点（方案 B）：CN 手机号+验证码 / 微信后绑手机；GL Email / Google / Apple。

路由前缀 /auth/*：
  POST /auth/sms/send        发送短信验证码（CN）
  POST /auth/sms/verify      验证码登录/注册（CN）
  POST /auth/wechat/callback 微信 OAuth 回调 → 若未绑手机返回 bind_token
  POST /auth/wechat/bind-phone 微信登录后绑手机号（绑定即登录）
  POST /auth/email/send      发送邮箱验证码（GL）
  POST /auth/email/verify    邮箱验证码登录/注册（GL）
  POST /auth/oauth/google    Google id_token 登录/注册（GL）
  POST /auth/oauth/apple     Apple id_token 登录/注册（GL）
  POST /auth/refresh         刷新令牌轮换
  POST /auth/logout          撤销刷新令牌
  GET  /auth/providers       登录页方式清单（按 region 渲染）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import AuthIdentity, User
from ..modules import auth as A

router = APIRouter()


def _ensure_login_ready(kind: str = "jwt") -> None:
    """生产 fail-loud：按端点类型校验所需配置，缺任一 → 503，绝不静默降级。

    kind: jwt | sms | email | wechat | google | apple
    """
    st = get_settings()
    if st.env != "prod":
        return
    if not st.jwt_secret:
        raise HTTPException(503, "认证服务未配置：JQ_JWT_SECRET 缺失")
    if st.auth_stub:
        raise HTTPException(503, "认证服务未配置：生产禁止 auth_stub（会伪造验证码）")
    if kind == "sms" and st.sms_provider == "stub":
        raise HTTPException(503, "短信通道未接入：JQ_SMS_PROVIDER=tencent + 短信密钥/模板")
    if kind == "email" and st.email_provider == "stub":
        raise HTTPException(503, "邮件通道未接入：JQ_EMAIL_PROVIDER=resend + JQ_RESEND_API_KEY")
    if kind == "wechat" and not (st.wechat_app_id and st.wechat_app_secret):
        raise HTTPException(503, "微信登录未接入：JQ_WECHAT_APP_ID / JQ_WECHAT_SECRET")
    if kind == "google" and not st.google_client_id:
        raise HTTPException(503, "Google 登录未接入：JQ_GOOGLE_CLIENT_ID")
    if kind == "apple" and not st.apple_client_id:
        raise HTTPException(503, "Apple 登录未接入：JQ_APPLE_CLIENT_ID")


class SendBody(BaseModel):
    phone: str | None = None
    email: str | None = None
    purpose: str = "login"


class VerifySmsBody(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)
    purpose: str = "login"
    device_token: str | None = None  # 游客设备账户：登录时合并注单/记忆/关注


class VerifyEmailBody(BaseModel):
    email: str
    code: str = Field(min_length=4, max_length=8)
    device_token: str | None = None


class WechatBody(BaseModel):
    code: str


class WechatBindBody(BaseModel):
    bind_token: str
    phone: str
    code: str = Field(min_length=4, max_length=8)


class OAuthBody(BaseModel):
    id_token: str


class RefreshBody(BaseModel):
    refresh_token: str


# ---------- 发送验证码 ----------

@router.post("/auth/sms/send")
def sms_send(body: SendBody, request: Request, db: Session = Depends(get_db)):
    _ensure_login_ready("sms")
    phone = (body.phone or "").strip()
    if not A.PHONE_RE.match(phone):
        raise HTTPException(422, "手机号格式不正确（中国大陆 11 位）")
    try:
        r = A.send_code(db, "sms", phone, body.purpose,
                        ip=request.client.host if request.client else None)
    except RuntimeError as e:
        raise HTTPException(503, f"短信通道不可用：{e}")
    if not r["ok"]:
        raise HTTPException(429, detail={"error": "too_many_requests",
                                         "retry_after": r.get("retry_after", 60)})
    return r


@router.post("/auth/email/send")
def email_send(body: SendBody, request: Request, db: Session = Depends(get_db)):
    _ensure_login_ready("email")
    email = (body.email or "").strip().lower()
    if not A.EMAIL_RE.match(email):
        raise HTTPException(422, "邮箱格式不正确")
    try:
        r = A.send_code(db, "email", email, body.purpose,
                        ip=request.client.host if request.client else None)
    except RuntimeError as e:
        raise HTTPException(503, f"邮件通道不可用：{e}")
    if not r["ok"]:
        raise HTTPException(429, detail={"error": "too_many_requests",
                                         "retry_after": r.get("retry_after", 60)})
    return r


# ---------- 验证码登录（CN / GL） ----------

@router.post("/auth/sms/verify")
def sms_verify(body: VerifySmsBody, db: Session = Depends(get_db)):
    _ensure_login_ready("sms")
    phone = body.phone.strip()
    if not A.PHONE_RE.match(phone):
        raise HTTPException(422, "手机号格式不正确")
    if not A.verify_code(db, "sms", phone, body.code, body.purpose or "login"):
        raise HTTPException(401, "验证码错误或已过期")
    user, created = A.get_or_create_by_phone(db, phone)
    A.link_identity(db, user, "phone", phone, A.mask_phone(phone))
    merged = A.merge_device_account(db, body.device_token, user, new_user=created)
    return {"created": created, "user": A.public_user(user),
            "merged": merged, **A.tokens_for(db, user)}


@router.post("/auth/email/verify")
def email_verify(body: VerifyEmailBody, db: Session = Depends(get_db)):
    _ensure_login_ready("email")
    email = body.email.strip().lower()
    if not A.EMAIL_RE.match(email):
        raise HTTPException(422, "邮箱格式不正确")
    if not A.verify_code(db, "email", email, body.code, "login"):
        raise HTTPException(401, "验证码错误或已过期")
    user, created = A.get_or_create_by_email(db, email)
    merged = A.merge_device_account(db, body.device_token, user, new_user=created)
    return {"created": created, "user": A.public_user(user),
            "merged": merged, **A.tokens_for(db, user)}


# ---------- 微信（CN）：登录后必须绑手机 ----------

@router.post("/auth/wechat/callback")
def wechat_callback(body: WechatBody, db: Session = Depends(get_db)):
    _ensure_login_ready("wechat")
    wx = A.wechat_exchange(body.code)
    if not wx:
        raise HTTPException(401, "微信授权失败")
    user = A.find_user_by_identity(db, "wechat", wx["openid"])
    if user is not None:
        if user.phone_verified:
            return {"needs_phone_bind": False, "user": A.public_user(user),
                    **A.tokens_for(db, user)}
        return {"needs_phone_bind": True,
                "bind_token": _bind_token(wx["openid"]),
                "reason": "该微信账号尚未绑定手机号"}
    # 新微信用户：先发 bind_token，绑手机后建号
    return {"needs_phone_bind": True,
            "bind_token": _bind_token(wx["openid"]),
            "reason": "首次微信登录需绑定手机号（合规要求）"}


def _bind_token(openid: str) -> str:
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    secret = A._secret()
    exp = datetime.now(timezone.utc) + timedelta(minutes=10)
    return pyjwt.encode({"typ": "wechat_bind", "openid": openid,
                         "exp": int(exp.timestamp())}, secret, algorithm="HS256")


def _read_bind_token(token: str) -> str | None:
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token, A._secret(), algorithms=["HS256"])
    except Exception:
        return None
    return payload.get("openid") if payload.get("typ") == "wechat_bind" else None


@router.post("/auth/wechat/bind-phone")
def wechat_bind_phone(body: WechatBindBody, db: Session = Depends(get_db)):
    _ensure_login_ready("sms")
    openid = _read_bind_token(body.bind_token)
    if not openid:
        raise HTTPException(401, "绑定凭证无效或已过期，请重新微信授权")
    phone = body.phone.strip()
    if not A.PHONE_RE.match(phone):
        raise HTTPException(422, "手机号格式不正确")
    if not A.verify_code(db, "sms", phone, body.code, "wechat_bind"):
        raise HTTPException(401, "验证码错误或已过期")
    user, created = A.get_or_create_by_phone(db, phone)
    try:
        A.link_identity(db, user, "wechat", openid, "wechat:" + openid[:8])
    except ValueError:
        raise HTTPException(409, "该微信已绑定其他账号")
    return {"created": created, "bound": ["wechat", "phone"],
            "user": A.public_user(user), **A.tokens_for(db, user)}


@router.post("/auth/wechat/bind-phone/send")
def wechat_bind_send(body: SendBody, request: Request, db: Session = Depends(get_db)):
    """微信绑定流程专用的验证码发送（purpose=wechat_bind）。"""
    _ensure_login_ready("sms")
    phone = (body.phone or "").strip()
    if not A.PHONE_RE.match(phone):
        raise HTTPException(422, "手机号格式不正确")
    try:
        r = A.send_code(db, "sms", phone, "wechat_bind",
                        ip=request.client.host if request.client else None)
    except RuntimeError as e:
        raise HTTPException(503, f"短信通道不可用：{e}")
    if not r["ok"]:
        raise HTTPException(429, detail={"error": "too_many_requests",
                                         "retry_after": r.get("retry_after", 60)})
    return r


# ---------- Google / Apple（GL） ----------

@router.post("/auth/oauth/google")
def oauth_google(body: OAuthBody, db: Session = Depends(get_db)):
    return _oauth_login(db, "google", body.id_token)


@router.post("/auth/oauth/apple")
def oauth_apple(body: OAuthBody, db: Session = Depends(get_db)):
    return _oauth_login(db, "apple", body.id_token)


def _oauth_login(db: Session, provider: str, id_token: str):
    _ensure_login_ready(provider)
    info = A.verify_oauth(provider, id_token)
    if not info or not info.get("sub"):
        raise HTTPException(401, "第三方登录校验失败")
    sub = info["sub"]
    user = A.find_user_by_identity(db, provider, sub)
    created = False
    if user is not None and user.deleted_at is not None:
        user.deleted_at = None  # 登录 = 撤回注销
        db.commit()
    if user is None:
        email = (info.get("email") or "").lower() or None
        # 同邮箱已注册 → 合并到既有用户（仅当邮箱已验证；该用户未绑同 provider 其他账号）
        if email and info.get("email_verified"):
            candidate = db.scalar(select(User).where(User.email == email))
            if candidate is not None:
                bound = db.scalar(select(AuthIdentity).where(
                    AuthIdentity.user_id == candidate.id, AuthIdentity.provider == provider))
                if bound is not None:
                    raise HTTPException(
                        409, f"该邮箱已绑定其他 {provider} 账号，请使用原方式登录")
                user = candidate
        if user is None:
            user = A.create_user(db, "global", email=email if info.get("email_verified") else None)
            created = True
        try:
            A.link_identity(db, user, provider, sub, f"{provider}:{sub[:8]}")
        except ValueError as e:
            raise HTTPException(409, str(e))
    return {"created": created, "provider": provider,
            "user": A.public_user(user), **A.tokens_for(db, user)}


# ---------- 令牌生命周期 ----------

@router.post("/auth/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    _ensure_login_ready("jwt")
    out = A.rotate_refresh(db, body.refresh_token)
    if not out:
        raise HTTPException(401, "刷新令牌无效（可能已复用，整个会话族已撤销）")
    return out


@router.post("/auth/logout")
def logout(body: RefreshBody, db: Session = Depends(get_db)):
    A.revoke_refresh(db, body.refresh_token)
    return {"ok": True}


# ---------- 登录页方式清单 ----------

@router.get("/auth/providers")
def auth_providers(region: str = "cn"):
    if region == "global":
        return {"region": "global", "providers": [
            {"id": "email", "label": "Email 验证码", "primary": True},
            {"id": "google", "label": "Google 登录"},
            {"id": "apple", "label": "Apple 登录"}]}
    return {"region": "cn", "providers": [
        {"id": "phone", "label": "手机号验证码", "primary": True},
        {"id": "wechat", "label": "微信登录（需绑定手机号）"}]}
