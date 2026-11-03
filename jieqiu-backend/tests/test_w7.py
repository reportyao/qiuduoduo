"""W7 测试：F20 分享编号可验（双向）、F18 两区域登录回归、导出、注销清除、深链。"""
from datetime import datetime, timedelta
from sqlalchemy import select

from app.models import (Bet, MatchResult, Memory, ShareCard, SPMatch, SPSnapshot,
                        User, Verdict)
from app.modules import verdict as vz
from app.modules.share import MARKET_PROFILES, verify_share
from app.modules.users import login_device, purge_expired_deletions, upsert_memory
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


def _mini(monkeypatch, conf=0.45):
    import os
    import tempfile
    import pandas as pd
    from app.config import Settings
    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(24):
        d = base + pd.Timedelta(days=i)
        if i % 2 == 0:
            rows.append(dict(datetime=d, team_home="霸主", team_away="弱旅", xg_home=3.0, xg_away=0.6))
        else:
            rows.append(dict(datetime=d, team_home="弱旅", team_away="霸主", xg_home=0.7, xg_away=2.6))
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    pd.DataFrame(rows).to_csv(path, index=False)
    s2 = Settings(xg_data_path=path, model_conf_threshold=conf,
                  market_div_threshold=0.30, rake_clamp_lo=0.10)
    monkeypatch.setattr(vz, "get_settings", lambda: s2)


def _promotable(db, mid="2056001", no="周六001"):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    kc = datetime.strptime(future_kickoff(today_cn()), "%Y-%m-%d %H:%M:%S")
    db.merge(__import__("app.models", fromlist=["IntlOdds"]).IntlOdds(
        source="pinnacle", sport="soccer_epl", league="EPL",
        home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
        kickoff_utc=(kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        sp_h=1.42, sp_d=4.50, sp_a=6.80, retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.commit()


# ---------- F20：分享编号可验（gate：双向） ----------

def test_share_verdict_verifiable(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable(db)
    build_verdicts(db, today_cn(), NOW)
    vid = db.scalars(select(Verdict)).first().id
    # 生成
    r = client.post(f"/share/verdict/{vid}").json()
    sid = r["share_id"]
    assert len(sid) == 12 and r["deep_link"] == f"jieqiu://share/{sid}"
    # 验证：match True
    v = client.get(f"/share/{sid}").json()
    assert v["match"] is True and v["content_hash"] == v["recomputed_hash"]
    assert v["payload"]["kind"] == "verdict"
    assert v["verdict_seal_url"].startswith("/verdicts/")
    # 幂等：同判决再分享 → 同编号
    r2 = client.post(f"/share/verdict/{vid}").json()
    assert r2["share_id"] == sid
    # 幂等根因：内容不含时间戳（连续两次毫秒间隔也必须同编号）
    r3 = client.post(f"/share/verdict/{vid}", params={"persona": "laopao"}).json()
    # 不同人设是不同内容 → 不同编号（合法）
    assert r3["share_id"] != sid
    # 篡改 → match False（gate 反向）
    card = db.get(ShareCard, sid)
    card.payload = dict(card.payload, text="被篡改的话术")
    db.commit()
    v2 = client.get(f"/share/{sid}").json()
    assert v2["match"] is False  # 编号验证暴露篡改


def test_share_weekly_and_streak(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable(db)
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-share"})
    tok = {"Authorization": "Bearer tok-share"}
    uid = client.get("/me", headers=tok).json()["user_id"]
    db.add(Bet(user_id=uid, verdict_id=db.scalars(select(Verdict)).first().id,
               amount=100, pick_dir="主胜"))
    db.commit()
    w = client.post("/share/weekly", headers=tok).json()
    assert w["share_id"] and w["text"]
    s = client.post("/share/streak", headers=tok).json()
    assert s["share_id"]
    mine = client.get("/shares/mine", headers=tok).json()
    assert {m["kind"] for m in mine} == {"weekly", "streak"}


# ---------- F18：双区域登录回归（gate） ----------

def test_two_region_login_regression(db, client):
    """F18 gate：两区域登录回归。"""
    rc = client.post("/auth/device", json={"device_token": "tok-cn", "region": "cn"}).json()
    rg = client.post("/auth/device", json={"device_token": "tok-global", "region": "global"}).json()
    assert rc["region"] == "cn" and rg["region"] == "global"
    # 非法区域
    assert client.post("/auth/device", json={"device_token": "tok-x", "region": "mars"}).status_code == 422
    # profile 差异
    pc = client.get("/me/market-profile", headers={"Authorization": "Bearer tok-cn"}).json()
    pg = client.get("/me/market-profile", headers={"Authorization": "Bearer tok-global"}).json()
    assert "12356" in pc["helpline"] and "未满 18" in pc["compliance"]
    assert "begambleaware" in pg["helpline"].lower() and "18+" in pg["compliance"]
    assert pc["currency"] == "CNY" and pg["currency"] == "USD"


# ---------- /me/export ----------

def test_me_export(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable(db)
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-export"})
    tok = {"Authorization": "Bearer tok-export"}
    vid = db.scalars(select(Verdict)).first().id
    client.post("/bets", json={"verdict_id": vid, "amount": 100}, headers=tok)
    client.put("/me/memories/主队偏好", json={"value": "曼城"}, headers=tok)
    ex = client.get("/me/export", headers=tok).json()
    assert len(ex["bets"]) == 1 and len(ex["memories"]) == 1
    assert "device_token" not in str(ex["user"])  # 令牌绝不导出
    assert ex["user"]["region"] == "cn"


# ---------- 注销期满清除 ----------

def test_purge_expired_deletions(db):
    """期满清除：过冷静期用户连数据一起删；冷静期内/活跃用户保留。"""
    from datetime import timezone
    old_user, _ = login_device(db, "tok-old")
    old_user.deleted_at = datetime.now(timezone.utc) - timedelta(days=8)
    fresh_user, _ = login_device(db, "tok-fresh")
    fresh_user.deleted_at = datetime.now(timezone.utc) - timedelta(days=2)  # 冷静期内
    active, _ = login_device(db, "tok-active")
    db.commit()
    # 各挂一条记忆
    upsert_memory(db, old_user.id, "k1", "v1")
    upsert_memory(db, fresh_user.id, "k2", "v2")
    counts = purge_expired_deletions(db, days=7)
    assert counts["purged_users"] == 1
    assert db.get(User, old_user.id) is None
    assert db.get(User, fresh_user.id) is not None       # 冷静期内保留
    assert db.get(User, active.id) is not None           # 活跃用户保留
    assert db.scalars(select(Memory).where(Memory.user_id == old_user.id)).all() == []
    assert db.scalars(select(Memory).where(Memory.user_id == fresh_user.id)).all() != []
    # 撤回语义不受影响：fresh 重登录 → deleted_at 清空
    login_device(db, "tok-fresh")
    assert db.get(User, fresh_user.id).deleted_at is None


def test_share_public_html_page(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable(db)
    build_verdicts(db, today_cn(), NOW)
    vid = db.scalars(select(Verdict)).first().id
    r = client.post(f"/share/verdict/{vid}").json()
    page = client.get(f"/s/{r['share_id']}")
    assert page.status_code == 200
    assert "分享卡" in page.text and r["share_id"] in page.text
    assert client.get("/s/nope").status_code == 404
