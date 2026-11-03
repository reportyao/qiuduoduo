"""API 集成测试：真实管线（建数据 → 判决 → stream/detail/seal）。"""
import sqlite3

from app.models import SPMatch, SPSnapshot
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn


def _seed_two_matches(db):
    """一场浅水单关（过价闸）+ 一场深水场（死价闸），kickoff 用未来时间。"""
    db.merge(SPMatch(match_id="2042501", match_no="周三012", league="英超",
                     home_raw="曼城", away_raw="布莱顿", home="曼城", away="布莱顿",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPMatch(match_id="2042502", match_no="周三001", league="英超",
                     home_raw="利物浦", away_raw="埃弗顿", home="利物浦", away="埃弗顿",
                     kickoff=future_kickoff(today_cn(), 23, 0), single_flag=True))
    cn_t = today_cn() + "T12:00:00+08:00"
    # 浅水：rake ≈ 5.6%（1.53/4.40/5.60，隐含和 1.0594）
    db.merge(SPSnapshot(match_id="2042501", pool="had", goal_line="",
                        sp_h=1.53, sp_d=4.40, sp_a=5.60, captured_at=cn_t))
    # 深水：rake ≈ 14.3%（1.20/4.50/9.00，隐含和 1.1667）→ 超阈值 12.6%
    db.merge(SPSnapshot(match_id="2042502", pool="had", goal_line="",
                        sp_h=1.20, sp_d=4.50, sp_a=9.00, captured_at=cn_t))
    db.commit()


def test_health(client, db):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["env"] == "test"
    assert body["db"]["backend"] == "sqlite" and body["db"]["latency_ms"] >= 0
    assert "counts" not in body  # 探针默认不跑大表 COUNT
    detailed = client.get("/health?detailed=1").json()
    assert "counts" in detailed and "sp_snapshots" in detailed["counts"]


def test_stream_full_pipeline(client, db):
    _seed_two_matches(db)
    vs = build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    assert len(vs) == 2

    r = client.get("/stream")
    assert r.status_code == 200
    body = r.json()
    assert body["trade_date"] == today_cn()
    assert body["stats"]["total"] == 2
    # 浅水场过价闸 → screening（市/模 W3 pending）；深水场死价闸
    assert body["stats"]["price_pass"] == 1
    assert body["stats"]["price_fail"] == 1
    assert body["stats"]["promoted"] == 0  # W2 市/模未接入，诚实为 0
    # 避雷 = 深水场，死因真实
    assert len(body["avoid"]) == 1
    av = body["avoid"][0]
    assert av["home"] == "利物浦" and abs(av["rake"] - 0.1429) < 0.001
    assert "抽水" in av["why"]
    # watch = 浅水场
    assert len(body["watch"]) == 1 and body["watch"][0]["home"] == "曼城"
    # 闸门结果与状态一致
    w = body["watch"][0]
    assert w["gates"]["price"] == "pass" and w["gates"]["market"] == "pending_data"


def test_verdict_detail_and_seal(client, db):
    _seed_two_matches(db)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    vid = f"v{today_cn()}-周三012"

    r = client.get(f"/verdicts/{vid}")
    assert r.status_code == 200
    d = r.json()
    assert d["home"] == "曼城" and d["pool"] == "had"
    assert abs(d["probs"]["home"] - 0.6167) < 0.001
    assert abs(d["rake"] - 0.0561) < 0.001
    assert d["payload"]["engine"] == "jieqiu-w3.0"

    r2 = client.get(f"/verdicts/{vid}/seal")
    assert r2.status_code == 200
    s = r2.json()
    assert s["match"] is True
    assert len(s["stored_hash"]) == 64
    # 404
    assert client.get("/verdicts/nope").status_code == 404
    assert client.get("/verdicts/nope/seal").status_code == 404


def test_stream_bad_date(client):
    assert client.get("/stream", params={"date": "2026/11/03"}).status_code == 422


def test_real_collector_db_end_to_end(client, db, tmp_path):
    """端到端：合成 collector 库 → import_collector_db → build_verdicts → /stream。"""
    from app.modules.ingest import import_collector_db

    p = str(tmp_path / "sp_data.db")
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE matches (match_no TEXT, match_id TEXT, league TEXT,
          home TEXT, away TEXT, kickoff TEXT, single_flag INTEGER, PRIMARY KEY (match_id));
        CREATE TABLE sp_snapshots (match_id TEXT, pool TEXT, goal_line TEXT,
          sp_h REAL, sp_d REAL, sp_a REAL, captured_at TEXT,
          PRIMARY KEY (match_id, pool, captured_at));
        """
    )
    kickoff = future_kickoff(today_cn())
    con.execute("INSERT INTO matches VALUES (?,?,?,?,?,?,?)",
                ("周三012", "2042501", "英超", "曼彻斯特城", "布莱顿", kickoff, 1))
    con.execute("INSERT INTO sp_snapshots VALUES (?,?,?,?,?,?,?)",
                ("2042501", "had", "", 1.53, 4.40, 5.60, "2026-11-05T19:00:00+08:00"))
    con.commit()
    con.close()

    import_collector_db(db, p)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    body = client.get("/stream").json()
    assert body["stats"]["total"] == 1
    assert body["watch"][0]["home"] == "曼城"  # 对齐后
