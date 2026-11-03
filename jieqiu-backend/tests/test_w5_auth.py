"""W5 认证测试：CN 手机号/微信绑手机；GL 邮箱/Google/Apple；JWT/refresh 安全。"""
import time

from sqlalchemy import select

from app.models import AuthIdentity, RefreshToken, User
from app.modules import auth as A
from app.modules.users import user_from_token
from tests.conftest import today_cn


def _reset_limits():
    A._last_send.clear()
    A._daily_count.clear()
    A._ip_sends.clear()


def _send_and_verify(client, channel: str, target: str, purpose="login"):
    _reset_limits()
    body = {"phone": target} if channel == "sms" else {"email": target}
    if purpose != "login":
        r = client.post(f"/auth/{channel}/send", json={**body, "purpose": purpose})
    else:
        r = client.post(f"/auth/{channel}/send", json=body)
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    if channel == "sms":
        return client.post("/auth/sms/verify", json={"phone": target, "code": code, "purpose": purpose})
    return client.post("/auth/email/verify", json={"email": target, "code": code})


# ---------- CN：手机号 ----------

def test_phone_register_and_login(db, client):
    r = _send_and_verify(client, "sms", "13800138000")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    u = body["user"]
    assert u["region"] == "cn" and u["phone"] == "138****8000" and u["phone_verified"]
    assert body["access_token"] and body["refresh_token"]

    # 再次登录：同一用户、created=False
    r2 = _send_and_verify(client, "sms", "13800138000")
    b2 = r2.json()
    assert b2["created"] is False and b2["user"]["user_id"] == u["user_id"]
    assert len(db.scalars(select(User)).all()) == 1

    # JWT 可访问 /me
    me = client.get("/me", headers={"Authorization": "Bearer " + b2["access_token"]})
    assert me.status_code == 200 and me.json()["user_id"] == u["user_id"]


def test_phone_format_validation(db, client):
    assert client.post("/auth/sms/send", json={"phone": "12345"}).status_code == 422
    assert client.post("/auth/sms/send", json={"phone": "23800138000"}).status_code == 422


def test_code_wrong_and_single_use(db, client):
    _reset_limits()
    r = client.post("/auth/sms/send", json={"phone": "13900139000"})
    code = r.json()["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/auth/sms/verify", json={"phone": "13900139000", "code": wrong}).status_code == 401
    ok = client.post("/auth/sms/verify", json={"phone": "13900139000", "code": code})
    assert ok.status_code == 200
    # 单次消费：再用同码 → 401
    assert client.post("/auth/sms/verify", json={"phone": "13900139000", "code": code}).status_code == 401


def test_send_rate_limit(db, client):
    _reset_limits()
    assert client.post("/auth/sms/send", json={"phone": "13700137000"}).status_code == 200
    r = client.post("/auth/sms/send", json={"phone": "13700137000"})
    assert r.status_code == 429  # 60s 内第二条


# ---------- CN：微信后绑手机 ----------

def test_wechat_login_requires_phone_bind(db, client):
    _reset_limits()
    r = client.post("/auth/wechat/callback", json={"code": "wxcode-abc"})
    assert r.status_code == 200
    b = r.json()
    assert b["needs_phone_bind"] is True and b["bind_token"]
    # 未绑手机无法直接登录
    assert "access_token" not in b
    # 发绑定验证码（purpose=wechat_bind）→ 绑定成功
    s = client.post("/auth/wechat/bind-phone/send", json={"phone": "13600136000", "purpose": "wechat_bind"})
    code = s.json()["dev_code"]
    r2 = client.post("/auth/wechat/bind-phone",
                     json={"bind_token": b["bind_token"], "phone": "13600136000", "code": code})
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["created"] is True and "wechat" in b2["bound"] and b2["user"]["phone_verified"]
    # 再次微信登录 → 直接出令牌
    r3 = client.post("/auth/wechat/callback", json={"code": "wxcode-abc"})
    b3 = r3.json()
    assert b3["needs_phone_bind"] is False and b3["access_token"]
    assert b3["user"]["user_id"] == b2["user"]["user_id"]


def test_wechat_bind_merges_existing_phone_user(db, client):
    """微信后绑的手机号若已注册 → 合并到老用户（不建重复账号）。"""
    r = _send_and_verify(client, "sms", "13500135000")
    old_uid = r.json()["user"]["user_id"]
    _reset_limits()
    w = client.post("/auth/wechat/callback", json={"code": "wxcode-merge"}).json()
    s = client.post("/auth/wechat/bind-phone/send", json={"phone": "13500135000", "purpose": "wechat_bind"})
    code = s.json()["dev_code"]
    r2 = client.post("/auth/wechat/bind-phone",
                     json={"bind_token": w["bind_token"], "phone": "13500135000", "code": code})
    b = r2.json()
    assert b["created"] is False and b["user"]["user_id"] == old_uid
    assert len(db.scalars(select(User)).all()) == 1


def test_wechat_bind_token_forged_rejected(db, client):
    r = client.post("/auth/wechat/bind-phone",
                    json={"bind_token": "forged.token.value", "phone": "13400134000", "code": "123456"})
    assert r.status_code == 401


# ---------- GL：邮箱 ----------

def test_email_register_and_login(db, client):
    r = _send_and_verify(client, "email", "user@example.com")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["created"] is True and b["user"]["region"] == "global"
    assert b["user"]["email"] == "u***@example.com" and b["user"]["email_verified"]
    r2 = _send_and_verify(client, "email", "user@example.com")
    assert r2.json()["created"] is False
    # 大小写归一
    assert r2.json()["user"]["email"] == "u***@example.com"


# ---------- GL：Google / Apple ----------

def test_google_login_and_account_merge(db, client):
    r = client.post("/auth/oauth/google",
                    json={"id_token": "stub:google:g-123:user@example.com"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["created"] is True and b["provider"] == "google"
    assert b["user"]["region"] == "global" and b["user"]["email_verified"] is True
    uid = b["user"]["user_id"]
    # 同 Google sub 再登录 → 同用户
    b2 = client.post("/auth/oauth/google",
                     json={"id_token": "stub:google:g-123:user@example.com"}).json()
    assert b2["created"] is False and b2["user"]["user_id"] == uid
    # 邮箱已存在（上例 email 用户）→ 合并，不重复建号
    n_before = len(db.scalars(select(User)).all())
    b3 = client.post("/auth/oauth/google",
                     json={"id_token": "stub:google:g-999:user@example.com"}).json()
    assert len(db.scalars(select(User)).all()) == n_before, "同邮箱应合并而非新建"


def test_apple_login(db, client):
    r = client.post("/auth/oauth/apple",
                    json={"id_token": "stub:apple:a-1:appleuser@icloud.com"})
    assert r.status_code == 200
    assert r.json()["provider"] == "apple"
    # Apple 隐藏邮箱（无 email）也能建号
    r2 = client.post("/auth/oauth/apple", json={"id_token": "stub:apple:a-2:"})
    assert r2.status_code == 200 and r2.json()["created"] is True


def test_oauth_invalid_token_rejected(db, client):
    assert client.post("/auth/oauth/google", json={"id_token": "garbage"}).status_code == 401
    assert client.post("/auth/oauth/apple", json={"id_token": "stub:google:x:y"}).status_code == 401


# ---------- JWT / refresh 安全 ----------

def test_refresh_rotation_and_reuse_detection(db, client):
    r = _send_and_verify(client, "sms", "13300133000").json()
    rt = r["refresh_token"]
    # 轮换
    r1 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r1.status_code == 200
    new_rt = r1.json()["refresh_token"]
    assert new_rt != rt
    # 复用旧 token → 401 且整个 family 撤销
    r2 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 401
    # family 内新 token 也被撤销
    r3 = client.post("/auth/refresh", json={"refresh_token": new_rt})
    assert r3.status_code == 401


def test_logout_revokes_refresh(db, client):
    r = _send_and_verify(client, "sms", "13200132000").json()
    assert client.post("/auth/logout", json={"refresh_token": r["refresh_token"]}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": r["refresh_token"]}).status_code == 401


def test_legacy_device_token_still_works(db, client):
    """兼容：旧设备令牌仍是有效 Bearer（免登录态）。"""
    r = client.post("/auth/device", json={"device_token": "legacy-dev"})
    tok = r.json()["token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200


# ---------- 登录页方式清单 ----------

def test_auth_providers_by_region(client):
    cn = client.get("/auth/providers?region=cn").json()
    gl = client.get("/auth/providers?region=global").json()
    assert [p["id"] for p in cn["providers"]] == ["phone", "wechat"]
    assert [p["id"] for p in gl["providers"]] == ["email", "google", "apple"]
    assert cn["providers"][0]["primary"] is True and gl["providers"][0]["primary"] is True


# ---------- 二轮 review 回归 ----------

def test_ip_send_limit_blocks_sms_bombing(db, client):
    """同一 IP 对 21 个不同号码发码 → 第 21 个 429（防短信轰炸）。"""
    A._last_send.clear(); A._daily_count.clear(); A._ip_sends.clear()
    ok = 0
    limited = 0
    for i in range(21):
        r = client.post("/auth/sms/send", json={"phone": f"1390000{i:04d}"})
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 429:
            limited += 1
            break
    assert ok <= A._IP_HOURLY_LIMIT and limited == 1


def test_login_restores_soft_deleted_account(db, client):
    """手机号登录 = 撤回注销（与设备登录同语义）。"""
    _reset_limits()
    from app.modules.users import soft_delete
    r = _send_and_verify(client, "sms", "13100131000").json()
    uid = r["user"]["user_id"]
    u = db.get(User, uid)
    soft_delete(db, u)
    assert db.get(User, uid).deleted_at is not None
    r2 = _send_and_verify(client, "sms", "13100131000").json()
    assert r2["user"]["user_id"] == uid
    me = client.get("/me", headers={"Authorization": "Bearer " + r2["access_token"]})
    assert me.status_code == 200  # 410 已解除
    assert db.get(User, uid).deleted_at is None


def test_purge_removes_auth_identities_and_tokens(db):
    """注销期满清除必须带走手机号/邮箱/第三方标识与刷新令牌（隐私）。"""
    from datetime import datetime, timedelta, timezone
    from app.models import AuthIdentity, RefreshToken
    from app.modules.users import purge_expired_deletions
    u, _ = A.get_or_create_by_phone(db, "13000130000")
    A.issue_refresh(db, u)
    u.deleted_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.commit()
    assert db.scalars(select(AuthIdentity).where(AuthIdentity.user_id == u.id)).all()
    counts = purge_expired_deletions(db, days=7)
    assert counts["purged_users"] == 1
    assert counts["removed_identities"] >= 1 and counts["removed_tokens"] >= 1
    assert db.scalars(select(AuthIdentity).where(AuthIdentity.user_id == u.id)).all() == []
    assert db.get(User, u.id) is None


def test_export_includes_auth_fields(db, client):
    _reset_limits()
    r = _send_and_verify(client, "sms", "13000131000").json()
    ex = client.get("/me/export", headers={"Authorization": "Bearer " + r["access_token"]}).json()
    assert ex["user"]["phone"] == "13000131000"
    assert ex["user"]["phone_verified"] is True
    assert any(i["provider"] == "phone" for i in ex["auth_identities"])


def test_unique_phone_index_enforced(db):
    """数据库层唯一约束：同号二次插入必须失败（并发注册的最后防线）。"""
    from sqlalchemy.exc import IntegrityError
    import uuid as _uuid
    A.get_or_create_by_phone(db, "13000132000")
    dup = User(id=_uuid.uuid4().hex, device_token=_uuid.uuid4().hex,
               region="cn", phone="13000132000")
    db.add(dup)
    try:
        db.commit()
        assert False, "唯一索引未生效"
    except IntegrityError:
        db.rollback()


def test_login_merges_device_account_data(db, client):
    """游客先记注/记忆/关注，再手机号登录：数据必须跟到新账号，不能凭空丢失。"""
    from app.models import Bet, Memory, Verdict, WatchTarget
    from tests.conftest import future_kickoff

    guest = client.post("/auth/device", json={"device_token": "tok-merge-device"}).json()
    gid = guest["user_id"]
    db.merge(Verdict(id="v-merge-1", trade_date=today_cn(), match_id="2045999",
                     match_no="周四099", league="英超", home="甲", away="乙",
                     kickoff=future_kickoff(today_cn()), pool="had", goal_line="",
                     sp_h=1.8, sp_d=3.5, sp_a=4.2, rake=0.08,
                     p_home=0.55, p_draw=0.25, p_away=0.20,
                     status="promoted", gates={}, payload={"id": "v-merge-1"},
                     payload_hash="c" * 64, pick={"dir": "home"}))
    db.add(Bet(user_id=gid, verdict_id="v-merge-1", amount=88, pick_dir="home"))
    db.add(Memory(user_id=gid, key="主队偏好", value="曼城", source="你说过"))
    db.add(WatchTarget(user_id=gid, target_type="match", target_id="2045999"))
    db.commit()

    _reset_limits()
    send = client.post("/auth/sms/send", json={"phone": "13700137000"})
    code = send.json()["dev_code"]
    r = client.post("/auth/sms/verify", json={
        "phone": "13700137000", "code": code,
        "device_token": "tok-merge-device",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["merged"]["bets"] == 1
    assert body["merged"]["memories"] == 1
    assert body["merged"]["watches"] == 1
    uid = body["user"]["user_id"]

    assert db.scalar(select(Bet).where(Bet.verdict_id == "v-merge-1")).user_id == uid
    assert db.scalar(select(Memory).where(Memory.key == "主队偏好")).user_id == uid
    assert db.scalar(select(WatchTarget).where(WatchTarget.target_id == "2045999")).user_id == uid
    target = db.get(User, uid)
    assert target.device_token != "tok-merge-device"
    assert db.get(User, gid) is None
    # 合并后旧设备令牌不能再解析到手机号账号
    assert db.scalar(select(User).where(User.device_token == "tok-merge-device")) is None

    me = client.get("/me", headers={"Authorization": "Bearer " + body["access_token"]}).json()
    assert me["memories"][0]["value"] == "曼城"
