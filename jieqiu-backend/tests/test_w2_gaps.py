"""W2 补遗测试：stream 游标分页 + analysis-log + matches/on-sale。"""
from sqlalchemy.orm import Session  # noqa: F401

from app.models import SPMatch, SPSnapshot
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn


def _seed_n(db, n=3):
    # 固定在“次日 02:00”开赛：既晚于 build_verdicts 的固定 now，又落在
    # /matches/on-sale 的“次日 04:59 前”窗口内，避免测试随墙钟漂移（21:30 后跑会失败）。
    from datetime import datetime, timedelta
    from tests.conftest import CN
    now = datetime.now(CN)
    # 直接使用当前竞彩日：00:00–04:59 时 today_cn 已回退到前一日。
    target_day = today_cn()
    for i in range(n):
        mid = f"20426{i:02d}"
        db.merge(SPMatch(match_id=mid, match_no=f"周三{i:03d}", league="英超",
                         home_raw=f"球队{i}", away_raw="对手", home=f"球队{i}", away="对手",
                         kickoff=future_kickoff(target_day, 2, i), single_flag=True))
        # 递增抽水：1.53+i*0.1 → 深 → 排序可预期
        db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                            sp_h=1.50 + i * 0.1, sp_d=4.0, sp_a=6.0,
                            captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()


def test_stream_cursor_pagination(client, db):
    _seed_n(db, 3)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    r1 = client.get("/stream", params={"limit": 2})
    assert r1.status_code == 200
    b1 = r1.json()
    assert len(b1["verdicts"]) == 2
    assert b1["next_cursor"] is not None
    r2 = client.get("/stream", params={"limit": 2, "cursor": b1["next_cursor"]})
    b2 = r2.json()
    assert len(b2["verdicts"]) == 1
    assert b2["next_cursor"] is None  # 到底
    ids1 = {v["id"] for v in b1["verdicts"]}
    ids2 = {v["id"] for v in b2["verdicts"]}
    assert not ids1 & ids2  # 无重复


def test_stream_limit_clamped(client, db):
    _seed_n(db, 1)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    assert client.get("/stream", params={"limit": 99999}).status_code == 200
    assert client.get("/stream", params={"limit": 0}).status_code == 200


def test_analysis_log(client, db):
    _seed_n(db, 2)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    r = client.get("/analysis-log")
    assert r.status_code == 200
    b = r.json()
    assert b["date"] == today_cn()
    # 2 场 × 3 闸（price/market/model）= 6 条最新日志
    assert b["total"] == 6
    gates = {(e["match_no"], e["gate"]): e["result"] for e in b["entries"]}
    assert gates[("周三000", "price")] == "pass"
    assert gates[("周三000", "market")] == "pending_data"
    assert all(e["match"] for e in b["entries"])  # 场次名已联表


def test_analysis_log_empty_day(client, db):
    b = client.get("/analysis-log", params={"date": "2020-01-01"}).json()
    assert b["total"] == 0 and b["entries"] == []


def test_matches_on_sale(client, db):
    _seed_n(db, 2)
    r = client.get("/matches/on-sale")
    assert r.status_code == 200
    b = r.json()
    assert b["count"] == 2
    assert {m["single"] for m in b["matches"]} == {True}
    assert b["matches"][0]["kickoff"] <= b["matches"][1]["kickoff"]  # 按开赛排序
