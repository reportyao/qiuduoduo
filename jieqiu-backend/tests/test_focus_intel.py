"""聚焦卡 / 数据脉搏 / 互动埋点。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import ModelRun, SPMatch, SPSnapshot, Verdict
from tests.conftest import admin_login, future_kickoff, today_cn


def _seed(db, *, status="promoted", with_model=True, match_id="focus-1", no="周三901"):
    kickoff = future_kickoff(today_cn())
    date = today_cn()
    db.merge(SPMatch(match_id=match_id, match_no=no, league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    db.merge(SPSnapshot(match_id=match_id, pool="had", goal_line="",
                        sp_h=1.80, sp_d=3.50, sp_a=4.20,
                        captured_at=date + "T12:00:00+08:00"))
    pick = {"dir": "主胜", "prob": 0.61, "sp": 1.80, "ev": 0.098} if with_model else None
    db.merge(Verdict(
        id=f"v-{match_id}", trade_date=date, match_id=match_id, match_no=no,
        league="英超", home="曼城", away="曼联", kickoff=kickoff,
        pool="had", goal_line="", sp_h=1.80, sp_d=3.50, sp_a=4.20,
        rake=0.121, p_home=0.56, p_draw=0.23, p_away=0.21,
        model_h=0.61 if with_model else None, model_d=0.22 if with_model else None,
        model_a=0.17 if with_model else None,
        pick=pick, rake_threshold=0.13, status=status,
        gates={"price": {"result": "pass"},
               "market": {"result": "pass" if with_model else "pending_data"},
               "model": {"result": "pass" if with_model else "pending_data"}},
        payload={"model": {"engine": "DC v1.1"} if with_model else None,
                 "data_cutoff": date + "T12:00:00+08:00",
                 "evidence": [{"tag": "已核验", "t": "SP", "d": "1.80", "src": "sporttery"}]},
        payload_hash="a" * 64,
        sealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    if with_model:
        db.merge(ModelRun(match_id=match_id, run_date=date, gate="model",
                          result="pass", detail={"pick": "主胜"}))
    db.commit()
    return kickoff, date


def test_pulse_counts_and_display_factor(client, db):
    _seed(db)
    r = client.get(f"/stats/pulse?date={today_cn()}")
    assert r.status_code == 200
    data = r.json()
    assert data["counts"]["matches"] == 1
    assert data["counts"]["sp_snapshots"] == 1
    assert data["counts"]["verdicts"] == 1
    assert data["counts"]["model_runs"] == 1
    assert data["counts"]["sealed_links"] == 1
    assert data["data_points"] == 5  # 3 + model_run 1 + evidence 1
    assert data["display"]["data_points"] == 15
    assert data["display"]["factor"] == 3
    assert data["outcomes"]["promoted"] == 1
    source_keys = {row["key"] for row in data["sources"]}
    assert {"sportmonks", "intel"} <= source_keys
    assert data["definition"]


def test_pulse_bad_date(client):
    assert client.get("/stats/pulse?date=not-a-date").status_code == 422


def test_focus_anonymous_capabilities(client, db):
    _seed(db)
    r = client.get("/matches/focus-1/focus")
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"]["status"] == "promoted"
    assert data["state"] == "promoted"
    assert data["capabilities"]["can_bet"] is False
    bet = next(a for a in data["actions"] if a["id"] == "bet")
    assert bet["enabled"] is False and bet["reason"] == "login_required"
    assert any(f["kind"] == "price" for f in data["intel"]["facts"])
    assert data["interpretation"] is None


def test_focus_logged_in_and_already_bet(client, db):
    _seed(db)
    token = client.post("/auth/device", json={}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    data = client.get("/matches/focus-1/focus", headers=h).json()
    assert data["capabilities"]["can_bet"] is True
    r = client.post("/bets", json={"verdict_id": "v-focus-1", "amount": 10}, headers=h)
    assert r.status_code == 200, r.text
    data = client.get("/matches/focus-1/focus", headers=h).json()
    assert data["capabilities"]["can_bet"] is False
    bet = next(a for a in data["actions"] if a["id"] == "bet")
    assert bet["reason"] == "already_bet"


def test_focus_screening_and_missing(client, db):
    _seed(db, status="screening", with_model=False, match_id="focus-2", no="周三902")
    data = client.get("/matches/focus-2/focus").json()
    assert data["state"] == "screening"
    assert data["capabilities"]["can_why_not"] is True
    assert any(a["id"] == "why_not" for a in data["actions"])
    assert data["coverage"]["deep_eligible"] is False
    assert client.get("/matches/nope/focus").status_code == 404


def test_on_sale_includes_coverage(client, db):
    _seed(db)
    r = client.get("/matches/on-sale")
    assert r.status_code == 200
    item = r.json()["matches"][0]
    cov = item["coverage"]
    assert cov["score"] >= 10
    assert cov["level"] in ("full", "partial", "insufficient")
    assert "deep_eligible" in cov
    assert {s["key"] for s in cov["sources"]} >= {"price", "model", "lineups"}


def test_interactions_idempotent_and_whitelist(client):
    body = {"event": "focus_select", "event_id": "evt-12345678",
            "session_id": "s-1", "match_id": "m1"}
    r1 = client.post("/interactions", json=body)
    assert r1.status_code == 200 and r1.json()["duplicate"] is False
    r2 = client.post("/interactions", json=body)
    assert r2.status_code == 200 and r2.json()["duplicate"] is True
    bad = dict(body, event="unknown", event_id="evt-99999999")
    assert client.post("/interactions", json=bad).status_code == 422


def test_admin_ops_exposes_focus_intel_coverage(client, db):
    _seed(db)
    admin_login(client)
    ops = client.get("/admin/api/ops")
    assert ops.status_code == 200
    data = ops.json()
    assert data["interactions_24h"] == {}
    assert "football" in data and "alerts" in data


def test_verdict_viewed_event_allowed(client):
    r = client.post("/interactions", json={
        "event": "verdict_viewed", "event_id": "evt-view-0001",
        "session_id": "s-view", "match_id": "m1", "verdict_id": "v1",
    })
    assert r.status_code == 200
    assert r.json()["duplicate"] is False
