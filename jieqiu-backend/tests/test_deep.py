"""深度测试（多角度多形式）：冻结完整性、并发、模糊输入、全流程串联、安全卫生。"""
import json
import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Bet, IntlOdds, MatchResult, SPMatch, SPSnapshot, User, Verdict, VerdictRevision
from app.modules import verdict as vz
from app.modules.sealchain import build_anchor, verify_day
from app.modules.users import login_device, upsert_memory
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


def _promotable_match(db, mid, no, sp=(1.40, 4.60, 7.00)):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=sp[0], sp_d=sp[1], sp_a=sp[2],
                        captured_at=today_cn() + "T12:00:00+08:00"))
    kc = datetime.strptime(future_kickoff(today_cn()), "%Y-%m-%d %H:%M:%S")
    db.merge(IntlOdds(
        source="pinnacle", sport="soccer_epl", league="EPL",
        home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
        kickoff_utc=(kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        sp_h=1.42, sp_d=4.50, sp_a=6.80, retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.commit()


# ---------- 冻结完整性（深审查发现 1） ----------

def test_promoted_verdict_frozen_across_rebuilds(db, monkeypatch):
    """冻结纪律：promoted 判决重建时 hash/修订数不变（封存不可改写）。"""
    _mini(monkeypatch)
    _promotable_match(db, "2050001", "周五001")
    vs = build_verdicts(db, today_cn(), NOW)
    assert vs[0].status == "promoted"
    h1 = vs[0].payload_hash
    n_rev_1 = len(db.scalars(select(VerdictRevision)).all())
    # SP 移动 + 重跑 → promoted 不动
    db.merge(SPSnapshot(match_id="2050001", pool="had", goal_line="",
                        sp_h=1.10, sp_d=5.00, sp_a=9.00,
                        captured_at=today_cn() + "T14:00:00+08:00"))
    db.commit()
    vs2 = build_verdicts(db, today_cn(), "2026-11-03 20:00:00")
    assert vs2 == []  # 冻结：无更新
    v = db.get(Verdict, vs[0].id)
    assert v.payload_hash == h1  # 哈希未变
    assert len(db.scalars(select(VerdictRevision)).all()) == n_rev_1  # 无新修订


def test_settled_screening_verdict_frozen(db, monkeypatch):
    """已结算的 screening 判决同样冻结（结算即终局）。"""
    _mini(monkeypatch)
    _promotable_match(db, "2050002", "周五002")
    vs = build_verdicts(db, today_cn(), NOW)
    # 手动降格为 screening 并结算（模拟真实时序）
    v = db.get(Verdict, vs[0].id)
    v.status = "screening"
    v.settled = "lose"
    db.commit()
    n_before = len(db.scalars(select(VerdictRevision)).all())
    build_verdicts(db, today_cn(), "2026-11-03 20:00:00")
    assert len(db.scalars(select(VerdictRevision)).all()) == n_before


def test_killed_verdict_still_evolves(db, monkeypatch):
    """killed 保持可演化（重新入池机制的前提）。"""
    _mini(monkeypatch)
    # 深水 → killed
    db.merge(SPMatch(match_id="2050003", match_no="周五003", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2050003", pool="had", goal_line="",
                        sp_h=1.20, sp_d=4.50, sp_a=9.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    vs = build_verdicts(db, today_cn(), NOW)
    assert vs[0].status == "killed"
    n1 = len(db.scalars(select(VerdictRevision)).all())
    # 赔率改善 → 重建 → killed 演化（状态可能翻转，修订追加）
    db.merge(SPSnapshot(match_id="2050003", pool="had", goal_line="",
                        sp_h=1.45, sp_d=4.40, sp_a=6.50,
                        captured_at=today_cn() + "T14:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), "2026-11-03 20:00:00")
    assert len(db.scalars(select(VerdictRevision)).all()) > n1  # killed 仍活跃


# ---------- 链检索列 + 回填（深审查发现 2） ----------

def test_revision_trade_date_backfill(db, monkeypatch):
    _mini(monkeypatch)
    _promotable_match(db, "2050004", "周五004")
    build_verdicts(db, today_cn(), NOW)
    # 模拟历史 NULL
    for r in db.scalars(select(VerdictRevision)).all():
        r.trade_date = None
    db.commit()
    from app.modules.sealchain import backfill_revision_dates
    n = backfill_revision_dates(db)
    assert n >= 1
    # 检索走列后 verify 依旧通过
    build_anchor(db, today_cn())
    assert verify_day(db, today_cn())["ok"]


# ---------- 并发（深审查发现 3：真实 HTTP 服务器 + 多线程混合读写） ----------

def test_concurrent_real_http_server(monkeypatch):
    """真实并发：独立 uvicorn 子进程 + 12 线程混合读（最接近生产形态）。"""
    import os
    import subprocess
    import tempfile
    import time
    import urllib.request
    from app.config import Settings
    _mini(monkeypatch)
    fd, dbpath = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(dbpath)
    from sqlalchemy import create_engine
    from app.db import Base
    eng = create_engine(f"sqlite:///{dbpath}")
    Base.metadata.create_all(eng)
    from sqlalchemy.orm import Session
    s = Session(eng)
    s.merge(SPMatch(match_id="cc1", match_no="周六001", league="英超",
                    home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                    kickoff=future_kickoff(today_cn()), single_flag=True))
    s.merge(SPSnapshot(match_id="cc1", pool="had", goal_line="",
                       sp_h=1.40, sp_d=4.60, sp_a=7.00,
                       captured_at=today_cn() + "T12:00:00+08:00"))
    s.commit()
    env = dict(os.environ, JQ_DATABASE_URL=f"sqlite:///{dbpath}", JQ_XG_DATA_PATH="")
    port = 8101
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        ok = False
        for _ in range(30):
            time.sleep(0.3)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                ok = True
                break
            except Exception:
                continue
        assert ok, "子进程服务器未就绪"
        errors = []
        lock = threading.Lock()

        def worker(i):
            try:
                for j in range(8):
                    path = ["/stream", "/health", "/api/ledger"][j % 3]
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
                        if r.status >= 500:
                            with lock:
                                errors.append((i, j, r.status))
            except Exception as e:
                with lock:
                    errors.append((i, "exc", str(e)[:50]))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert not errors, f"并发错误: {errors[:3]}"
    finally:
        proc.terminate()
        try:
            os.remove(dbpath)
        except PermissionError:
            pass


# ---------- 安全卫生（深审查发现 4） ----------

def test_bet_amount_validation(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable_match(db, "2050006", "周五006")
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-amt"})
    tok = {"Authorization": "Bearer tok-amt"}
    vid = db.scalars(select(Verdict)).first().id
    for bad in (0, -5, 1e9):
        r = client.post("/bets", json={"verdict_id": vid, "amount": bad}, headers=tok)
        assert r.status_code == 422, f"amount={bad} 应被拒绝"
    assert client.post("/bets", json={"verdict_id": vid, "amount": 100}, headers=tok).status_code == 200


def test_memory_key_safety(db, client):
    client.post("/auth/device", json={"device_token": "tok-key"})
    tok = {"Authorization": "Bearer tok-key"}
    assert client.put("/me/memories/", json={"value": "x"}, headers=tok).status_code in (404, 405, 422)
    r = client.put("/me/memories/带%2F斜杠", json={"value": "x"}, headers=tok)
    assert r.status_code in (404, 422)  # 含 / 在路由层即被拒（安全属性）
    assert client.put("/me/memories/正常键", json={"value": "x"}, headers=tok).status_code == 200


def test_deleted_user_anonymous_stream(db, client, monkeypatch):
    """深审查发现 5：注销用户打 /stream 不泄露 you 块。"""
    _mini(monkeypatch)
    _promotable_match(db, "2050007", "周五007")
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-del2"})
    tok = {"Authorization": "Bearer tok-del2"}
    client.delete("/me", headers=tok)
    body = client.get("/stream", headers=tok).json()
    assert "you" not in body  # 降匿名


# ---------- 模糊输入（深审查发现 6：随机垃圾不产生 500） ----------

def test_fuzz_no_server_errors(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable_match(db, "2050008", "周五008")
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-fuzz"})
    tok = {"Authorization": "Bearer tok-fuzz"}
    vid = db.scalars(select(Verdict)).first().id
    nasty = [
        "", " " * 500, "🎉" * 300, "\x00\x01\x02", "a" * 5000,
        "'; DROP TABLE verdicts; --", "<script>alert(1)</script>",
        "%s%s%s%n", "\\\\..\\..\\windows\\system32", "日本語Deutschfrançais",
        None,
    ]
    for text in nasty:
        if text is None:
            r = client.post("/chat", json={})
        else:
            r = client.post("/chat", json={"text": text})
        assert r.status_code < 500, f"chat 崩溃于 {text!r:.30}"
    for date in ("2026-99-99", "not-a-date", "2026-02-30", "1970-01-01", "9999-12-31"):
        r = client.get("/stream", params={"date": date})
        assert r.status_code < 500, f"stream date={date} 崩溃"
    for cursor in ("!!!", "====", "eyJvZmZzZXQiOjk5OTk5OX0=", "a"):
        assert client.get("/stream", params={"cursor": cursor}).status_code < 500
    for persona in ("hacker", "<x>", "", "zhuanjia "):
        r = client.get(f"/verdicts/{vid}/narration.stream", params={"persona": persona})
        assert r.status_code < 500
    # 分页 limit 极值
    assert client.get("/stream", params={"limit": -5}).status_code == 200
    assert client.get("/stream", params={"limit": 10**9}).status_code == 200


# ---------- 全流程串联（多形式：登录→流→注单→结算→保护→复盘→账本） ----------

def test_full_user_journey(db, client, monkeypatch):
    _mini(monkeypatch)
    _promotable_match(db, "2050009", "周五009")
    vs = build_verdicts(db, today_cn(), NOW)
    vid = vs[0].id
    # 1 登录
    st, tok = 200, None
    r = client.post("/auth/device", json={"device_token": "tok-journey", "display_name": "旅程"})
    tok = {"Authorization": f"Bearer {r.json()['token']}"}
    # 2 流（you 块）
    s = client.get("/stream", headers=tok).json()
    assert s["mode"] == "normal" and s["you"]["protection_active"] is False
    # 3 记注
    r = client.post("/bets", json={"verdict_id": vid, "amount": 100}, headers=tok)
    assert r.status_code == 200
    bet_id = r.json()["id"]
    # 4 结算（赛果 0-1 → lose）
    v = db.get(Verdict, vid)
    v.settled = "lose"
    v.result_score = "0-1"
    db.commit()
    # 5 连败 2 场历史 + 本场 → 3 → 保护
    for i in range(2):
        v0 = Verdict(id=f"j{i}", trade_date="2026-11-03", match_id=f"j{i}",
                     match_no=f"周五90{i}", league="英超", home="A", away="B",
                     kickoff="2026-11-03 12:00:00", pool="had", goal_line="",
                     sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.6, p_draw=0.25,
                     p_away=0.15, status="promoted", gates={},
                     payload={"id": f"j{i}", "trade_date": "2026-11-03"},
                     payload_hash="e" * 64,
                     pick={"dir": "主胜", "prob": 0.6, "sp": 1.5, "ev": -0.1},
                     settled="lose", result_score="0-1")
        db.merge(v0)
        db.add(Bet(user_id=client.get("/me", headers=tok).json()["user_id"],
                   verdict_id=f"j{i}", amount=100, pick_dir="主胜"))
    db.commit()
    st_now = client.get("/me", headers=tok).json()["streak"]
    assert st_now["streak"] == 3 and st_now["active"]
    # 6 保护期加注 → 423（保护优先于重复检查——新语义）→ confirm 后到重复检查 409
    r = client.post("/bets", json={"verdict_id": vid, "amount": 50}, headers=tok)
    assert r.status_code == 423
    r = client.post("/bets", json={"verdict_id": vid, "amount": 50, "confirm": True},
                    headers=tok)
    assert r.status_code == 409  # confirm 后走到重复检查（同一判决已记）
    # 7 复盘
    pm = client.get(f"/verdicts/{vid}/postmortem").json()
    assert pm["kind"] == "promoted" and pm["attribution"]["settled"]
    bpm = client.get(f"/bets/{bet_id}/postmortem", headers=tok).json()
    assert bpm["bet"]["pnl"] == -100
    # 8 周报 + 账本
    w = client.get("/weekly-report", headers=tok).json()
    assert "you" in w and w["you"]["pnl"] < 0
    ledger = client.get("/api/ledger").json()
    assert any(it["id"] == vid for it in ledger["items"])
    # 9 链与锚
    build_anchor(db, today_cn())
    assert client.get("/chain/verify").json()["ok"]
