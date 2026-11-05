"""串关体检：四维分析、缺模型降级、输入校验。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import SPMatch, SPSnapshot, Verdict
from tests.conftest import admin_login, CN, future_kickoff, today_cn


def _seed(db, *, mid: str, no: str, model: bool, status: str = "promoted",
          vid: str | None = None, snap: bool = True):
    kickoff = future_kickoff(today_cn())
    date = today_cn()
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    if snap:
        db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                            sp_h=1.80, sp_d=3.50, sp_a=4.20,
                            captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.merge(Verdict(
        id=vid or f"v-{mid}", trade_date=date, match_id=mid, match_no=no,
        league="英超", home="曼城", away="曼联", kickoff=kickoff,
        pool="had", goal_line="", sp_h=1.80, sp_d=3.50, sp_a=4.20,
        rake=0.121, p_home=0.52, p_draw=0.27, p_away=0.21,
        model_h=0.56 if model else None,
        model_d=0.24 if model else None,
        model_a=0.20 if model else None,
        pick={"dir": "主胜", "prob": 0.56, "sp": 1.80} if model else None,
        rake_threshold=0.13, status=status,
        gates={"price": {"result": "pass"},
               "market": {"result": "pass" if model else "pending_data"},
               "model": {"result": "pass" if model else "pending_data"}},
        payload={"model": {"engine": "DC v1.1"} if model else None,
                 "data_cutoff": date + "T12:00:00+08:00",
                 "evidence": []},
        payload_hash=("a" if model else "b") * 64,
        sealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()


def test_parlay_check_full_model(client, db):
    _seed(db, mid="parlay-1", no="周三801", model=True)
    _seed(db, mid="parlay-2", no="周三802", model=True)
    r = client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "v-parlay-1", "dir": "home"},
            {"verdict_id": "v-parlay-2", "dir": "away"},
        ],
        "stake": 100,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["legs"]) == 2
    assert data["legs"][0]["model_prob"] == 0.56
    assert data["legs"][1]["model_prob"] == 0.20
    assert abs(data["combo"]["model_prob"] - 0.56 * 0.20) < 1e-9
    assert data["combo"]["model_coverage"] == "2/2"
    expected_cost = 100 - 100 * (1 - 0.121) ** 2
    assert abs(data["combo"]["cost"] - round(expected_cost, 2)) < 1e-9
    expected_model_return = 100 * (0.56 * 1.80) * (0.20 * 4.20)
    assert abs(data["combo"]["model_expected_return"] - round(expected_model_return, 2)) < 1e-9
    assert data["scores"]["model"] == "good"
    assert data["scores"]["structure"] == "high"
    assert data["legs"][0]["coverage"]["sources"]
    assert data["legs"][0]["facts"]
    assert data["data_cutoff"]
    assert data["summary"]


def test_parlay_check_missing_model_does_not_fake_combo(client, db):
    _seed(db, mid="parlay-3", no="周三803", model=True)
    _seed(db, mid="parlay-4", no="周三804", model=False, status="screening")
    data = client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "v-parlay-3", "dir": "home"},
            {"verdict_id": "v-parlay-4", "dir": "home"},
        ],
        "stake": 100,
    }).json()
    assert data["combo"]["model_coverage"] == "1/2"
    assert data["combo"]["model_prob"] is None
    assert data["combo"]["model_expected_return"] is None
    assert data["scores"]["model"] == "partial"
    assert any(x["key"] == "model_2" for x in data["optimizations"])
    assert any(x["key"] == "lineups_1" for x in data["optimizations"])


def test_parlay_check_rejects_duplicate_and_short(client, db):
    _seed(db, mid="parlay-5", no="周三805", model=True)
    _seed(db, mid="parlay-5", no="周三805", model=True, vid="v-parlay-5b", snap=False)
    assert client.post("/tools/parlay/check", json={
        "legs": [{"verdict_id": "v-parlay-5", "dir": "home"}],
    }).status_code == 422
    assert client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "v-parlay-5", "dir": "home"},
            {"verdict_id": "v-parlay-5", "dir": "away"},
        ],
    }).status_code == 422
    # 不同 verdict id、同一 match：也必须拒绝
    assert client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "v-parlay-5", "dir": "home"},
            {"verdict_id": "v-parlay-5b", "dir": "away"},
        ],
    }).status_code == 422


def test_parlay_check_four_legs_structure(client, db):
    for i in range(4):
        _seed(db, mid=f"four-{i}", no=f"周三81{i}", model=True)
    data = client.post("/tools/parlay/check", json={
        "legs": [{"verdict_id": f"v-four-{i}", "dir": "home"} for i in range(4)],
        "stake": 100,
    }).json()
    assert len(data["legs"]) == 4
    assert data["scores"]["structure"] == "high"
    assert any(x["key"] == "leg_count" for x in data["risks"])
    assert any(x["key"] == "leg_count" for x in data["optimizations"])


def test_parlay_check_rejects_five_legs(client, db):
    _seed(db, mid="five-0", no="周三820", model=True)
    legs = [{"verdict_id": "v-five-0", "dir": "home"} for _ in range(5)]
    assert client.post("/tools/parlay/check", json={"legs": legs}).status_code == 422


def test_parlay_check_flags_locked_leg(client, db):
    _seed(db, mid="locked-1", no="周三830", model=True)
    past = (datetime.now(CN) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    db.get(SPMatch, "locked-1").kickoff = past
    db.get(Verdict, "v-locked-1").kickoff = past
    _seed(db, mid="locked-2", no="周三831", model=True)
    db.commit()
    data = client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "v-locked-1", "dir": "home"},
            {"verdict_id": "v-locked-2", "dir": "home"},
        ],
    }).json()
    assert any(x["key"] == "lifecycle" for x in data["risks"])
    assert data["scores"]["structure"] in ("medium", "high")


def test_parlay_plan_generates_profiles(client, db):
    for i in range(3):
        _seed(db, mid=f"plan-{i}", no=f"周三84{i}", model=True)
    r = client.post("/tools/parlay/plan", json={"stake": 100})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["candidates"] == 3
    assert data["plans"]
    assert any(p["risk_profile"] == "conservative" for p in data["plans"])
    assert all(len(p["legs"]) >= 2 for p in data["plans"])
    assert all(p["check"]["combo"]["cost"] > 0 for p in data["plans"])


def test_parlay_plan_excludes_killed(client, db):
    _seed(db, mid="plan-kill", no="周三860", model=True, status="killed")
    _seed(db, mid="plan-ok1", no="周三861", model=True)
    _seed(db, mid="plan-ok2", no="周三862", model=True)
    data = client.post("/tools/parlay/plan", json={}).json()
    assert data["candidates"] == 2
    assert all("v-plan-kill" not in p["legs"] for p in data["plans"])


def test_parlay_plan_insufficient(client, db):
    _seed(db, mid="plan-one", no="周三850", model=True)
    data = client.post("/tools/parlay/plan", json={}).json()
    assert data["plans"] == []
    assert data["message"]


def test_admin_plans_preview(client, db):
    _seed(db, mid="plan-admin-1", no="周三870", model=True)
    _seed(db, mid="plan-admin-2", no="周三871", model=True)
    admin_login(client)
    r = client.get("/admin/api/plans-preview")
    assert r.status_code == 200
    data = r.json()
    assert "plans" in data and "candidates" in data


def test_parlay_plan_bad_date(client):
    assert client.post("/tools/parlay/plan", json={"date": "bad"}).status_code == 422


def test_parlay_check_missing_verdict(client):
    r = client.post("/tools/parlay/check", json={
        "legs": [
            {"verdict_id": "nope-1", "dir": "home"},
            {"verdict_id": "nope-2", "dir": "home"},
        ],
    })
    assert r.status_code == 404
