"""合规：年龄门/未成年锁定/自排除/休息中服务端硬拦截。"""
from __future__ import annotations

from tests.test_recommendations import _seed, _seed_market


def _device(client, token: str) -> dict:
    body = client.post("/auth/device", json={"device_token": token}).json()
    return {"Authorization": f"Bearer {body['token']}"}


def test_age_gate_and_under18_bet_block(client, db):
    headers = _device(client, "comp-age-1")
    state = client.get("/compliance/state", headers=headers).json()
    assert state["authenticated"] and state["under18_locked"] is False

    under = client.post("/gate/verify", headers=headers, json={"adult": False})
    assert under.status_code == 200 and under.json()["under18_locked"] is True
    _seed(db, mid="comp-under", no="周三981")
    blocked = client.post("/bets", headers=headers, json={
        "verdict_id": "v-comp-under", "amount": 10})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "under18"

    adult = client.post("/gate/verify", headers=headers, json={"adult": True})
    assert adult.status_code == 200 and adult.json()["under18_locked"] is False
    ok = client.post("/bets", headers=headers, json={
        "verdict_id": "v-comp-under", "amount": 10})
    assert ok.status_code == 200


def test_self_exclusion_blocks_bet_and_is_reported(client, db):
    headers = _device(client, "comp-excl-1")
    _seed_market(db, "comp-excl", "周三982")
    _seed(db, mid="comp-excl", no="周三982")
    r = client.post("/compliance/self-exclusion", headers=headers,
                    json={"days": 7, "reason": "test"})
    assert r.status_code == 200
    data = r.json()
    assert data["self_exclusion"]["active"] is True
    assert data["can_bet"] is False

    blocked = client.post("/bets", headers=headers, json={
        "verdict_id": "v-comp-excl", "amount": 10})
    assert blocked.status_code == 423
    assert blocked.json()["detail"]["error"] == "self_excluded"

    focus_resp = client.get("/matches/comp-excl/focus", headers=headers)
    assert focus_resp.status_code == 200, focus_resp.text
    focus = focus_resp.json()
    bet = next(a for a in focus["actions"] if a["id"] == "bet")
    assert bet["enabled"] is False and bet["reason"] == "self_excluded"


def test_rested_blocks_bet(client, db):
    headers = _device(client, "comp-rest-1")
    _seed(db, mid="comp-rest", no="周三983")
    assert client.post("/me/rest", headers=headers).status_code == 200
    blocked = client.post("/bets", headers=headers, json={
        "verdict_id": "v-comp-rest", "amount": 10})
    assert blocked.status_code == 423
    assert blocked.json()["detail"]["error"] == "rested"
