"""全量审计回归：性能下推、业务规则、安全加固的验证。"""
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import (AuthIdentity, IntlOdds, MatchResult, RefreshToken, SPMatch,
                        SPSnapshot, User, Verdict, VerdictRevision)
from app.modules import auth as A
from app.modules import verdict as vz
from app.modules.align import Aligner, seed_aliases
from app.modules.ingest import import_collector_db
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


def _mini(monkeypatch, conf=0.45):
    import os
    import tempfile
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


def _promotable(db, mid="2070001", no="周六101"):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    kc = datetime.strptime(future_kickoff(today_cn()), "%Y-%m-%d %H:%M:%S")
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=(kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                      sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T13:00:00+08:00"))
    db.commit()


# ---------- 性能修复的行为验证 ----------

def test_batch_ingest_2000_snapshots(db, tmp_path):
    """批量 upsert 正确性：2000 条快照一次导入，计数与内容都对。"""
    p = str(tmp_path / "big.db")
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE matches (match_no TEXT, match_id TEXT, league TEXT,
          home TEXT, away TEXT, kickoff TEXT, single_flag INTEGER, PRIMARY KEY (match_id));
        CREATE TABLE sp_snapshots (match_id TEXT, pool TEXT, goal_line TEXT,
          sp_h REAL, sp_d REAL, sp_a REAL, captured_at TEXT,
          PRIMARY KEY (match_id, pool, captured_at));
    """)
    con.execute("INSERT INTO matches VALUES ('周六001','3001','英超','曼城','布莱顿','2026-11-05 21:55:00',1)")
    for i in range(2000):
        t = f"2026-11-05T{10 + i // 3600:02d}:{(i // 60) % 60:02d}:{i % 60:02d}+08:00"
        con.execute("INSERT OR IGNORE INTO sp_snapshots VALUES (?,?,?,?,?,?,?)",
                    ("3001", "had", "", 1.5 + i * 0.0001, 4.4, 6.0, t))
    con.commit(); con.close()
    r = import_collector_db(db, p)
    assert r.snapshots_seen >= 1500 and r.snapshots_inserted == r.snapshots_seen
    assert len(db.scalars(select(SPSnapshot)).all()) == r.snapshots_inserted
    # 再导入 → 全部去重
    r2 = import_collector_db(db, p)
    assert r2.snapshots_inserted == 0


def test_results_sync_throttle(db, monkeypatch):
    """赛果同步 6h 节流：第二次不带 fetch 调用直接返回节流说明。"""
    from app.modules import settle as S
    monkeypatch.setattr(S, "_last_result_sync", lambda: datetime.now(S.CN).isoformat(timespec="seconds"))
    marks = []
    monkeypatch.setattr(S, "_mark_result_sync", lambda: marks.append(1))
    n, note = S.sync_results_football_data(db, Aligner(db))
    assert n == 0 and "节流" in note


def test_settle_ignores_old_verdicts(db):
    """30 天前的未结算判决不再进入扫描窗口（防全表永久扫描）。"""
    from app.modules.settle import settle_verdicts
    old_date = (datetime.now(timezone.utc) + timedelta(hours=8) - timedelta(days=40)).strftime("%Y-%m-%d")
    old = Verdict(id=f"v{old_date}-旧001", trade_date=old_date, match_id="old1",
                  match_no="旧001", league="英超", home="A", away="B",
                  kickoff=f"{old_date} 21:00:00", pool="had", goal_line="",
                  sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.6, p_draw=0.25,
                  p_away=0.15, status="promoted", gates={},
                  payload={"id": "old", "trade_date": old_date}, payload_hash="a" * 64,
                  pick={"dir": "主胜", "prob": 0.6, "sp": 1.5, "ev": -0.1})
    db.merge(old)
    db.merge(MatchResult(source="football-data", league="英超",
                         home="A", away="B", match_date=old_date,
                         goals_home=2, goals_away=0, retrieved_at="x"))
    db.commit()
    settle_verdicts(db)  # 窗口外 → 不结算
    assert db.get(Verdict, old.id).settled is None


def test_ledger_limit_pushdown(db, client):
    from app.models import Verdict as V
    for i in range(30):
        d = (datetime.now(timezone.utc) + timedelta(hours=8) - timedelta(days=i % 5)).strftime("%Y-%m-%d")
        db.merge(V(id=f"v{d}-L{i:02d}", trade_date=d, match_id=f"lm{i}",
                   match_no=f"L{i:02d}", league="英超", home="A", away="B",
                   kickoff=f"{d} 21:00:00", pool="had", goal_line="",
                   sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.6, p_draw=0.25,
                   p_away=0.15, status="screening", gates={},
                   payload={"id": f"lm{i}", "trade_date": d}, payload_hash="b" * 64))
    db.commit()
    r = client.get("/api/ledger", params={"limit": 5}).json()
    assert len(r["items"]) == 5
    page = client.get("/ledger")
    assert page.status_code == 200


def test_chain_status_cache_fingerprint(db, monkeypatch):
    """链状态缓存：内容不变命中；篡改后指纹变化 → 重新检测为断链。"""
    from app.modules.sealchain import build_anchor, latest_chain_status
    _mini(monkeypatch)
    _seed_one(db)
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    s1 = latest_chain_status(db)
    s2 = latest_chain_status(db)
    assert s1["ok"] and s2["ok"]
    rev = db.scalars(select(VerdictRevision)).first()
    rev.payload_hash = "f" * 64
    db.commit()
    s3 = latest_chain_status(db)
    assert s3["ok"] is False


def _seed_one(db):
    from app.models import VerdictRevision  # noqa
    db.merge(SPMatch(match_id="2080001", match_no="周六201", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2080001", pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()


# ---------- 业务规则修复验证 ----------

def test_chat_never_recommends_settled_match(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable(db, "2070010", "周六110")
    vs = build_verdicts(db, today_cn(), NOW)
    assert vs and vs[0].status == "promoted"
    v = vs[0]
    v.settled = "lose"
    db.commit()
    r = client.post("/chat", json={"text": "今晚买啥"}).json()
    assert "暂无" in r["text"] or "没有" in r["text"], r["text"]


def test_chat_memory_key_no_slash(db, client):
    client.post("/auth/device", json={"device_token": "tok-slash"})
    tok = {"Authorization": "Bearer tok-slash"}
    r = client.post("/chat", json={"text": "记住我的A/B是X"}, headers=tok).json()
    mems = client.get("/me/memories", headers=tok).json()
    assert mems and "/" not in mems[0]["key"]


# ---------- 安全加固验证 ----------

def test_console_login_lockout(db, client):
    from app.routers import console as C
    C._LOGIN_FAILS.clear()
    for _ in range(5):
        client.post("/console/login", data={"pw": "wrong"})
    r = client.post("/console/login", data={"pw": "wrong"})
    assert r.status_code == 429
    C._LOGIN_FAILS.clear()


def test_console_session_expiry(db, client):
    from app.routers import console as C
    C._LOGIN_FAILS.clear()
    r = client.post("/console/login", data={"pw": "dev"}, follow_redirects=False)
    tok = r.cookies.get("console_t")
    assert tok
    assert C._authed(type("R", (), {"cookies": {"console_t": tok}, "client": None})())
    C._SESSIONS[tok] = time.time() - 1  # 过期
    r2 = client.get("/console", follow_redirects=False)
    assert r2.status_code == 302


def test_device_login_can_be_disabled(db, client, monkeypatch):
    from app.config import Settings
    from app.routers import w6 as w6mod
    st = Settings(env="prod", allow_device_login=False, jwt_secret="x", auth_stub=False)
    monkeypatch.setattr(w6mod, "get_settings", lambda: st, raising=False)
    # w6 里是函数内 import，需要 patch app.config.get_settings
    import app.config as cfg
    monkeypatch.setattr(cfg, "get_settings", lambda: st)
    r = client.post("/auth/device", json={"device_token": "legacy"})
    assert r.status_code == 403


def test_memory_upsert_rejects_empty_key(db):
    u, _ = A.get_or_create_by_phone(db, "13000139000")
    from app.modules.users import upsert_memory
    with pytest.raises(ValueError):
        upsert_memory(db, u.id, "   ", "v")


def test_auth_stub_only_allowed_in_dev_test(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from app.config import Settings
    from app.routers import auth_w5
    monkeypatch.setattr(auth_w5, "get_settings",
                        lambda: Settings(env="dev", auth_stub=True, jwt_secret="x"))
    auth_w5._ensure_login_ready("sms")
    monkeypatch.setattr(auth_w5, "get_settings",
                        lambda: Settings(env="staging", auth_stub=True, jwt_secret="x"))
    with pytest.raises(HTTPException) as exc:
        auth_w5._ensure_login_ready("sms")
    assert exc.value.status_code == 503


def test_verification_code_attempt_limit_is_atomic(db):
    from app.modules import auth as A
    out = A.send_code(db, "sms", "13800138000", "login")
    code = out["dev_code"]
    wrong = "000000" if code != "000000" else "000001"
    for _ in range(5):
        assert A.verify_code(db, "sms", "13800138000", wrong, "login") is False
    assert A.verify_code(db, "sms", "13800138000", code, "login") is False


def test_request_body_size_guard(client):
    r = client.post("/chat", json={"text": "hi"},
                    headers={"Content-Length": "2000000"})
    assert r.status_code == 413


def test_share_streak_isolated_per_user(db):
    from app.models import User
    from app.modules.share import share_streak
    a = User(id="user-a", device_token="token-a")
    b = User(id="user-b", device_token="token-b")
    db.add_all([a, b])
    db.commit()
    ca, _ = share_streak(db, a)
    cb, _ = share_streak(db, b)
    assert ca.share_id != cb.share_id
    assert ca.payload["owner"] != cb.payload["owner"]
