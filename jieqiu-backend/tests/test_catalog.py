"""新增目录/成本 API 的契约与端到端测试。"""
from datetime import datetime, timedelta

from app.models import (Bet, Event, MatchResult, Notification, SPMatch,
                        SPSnapshot, User, Verdict, WatchTarget)
from app.modules.users import login_device
from app.modules.verdict import build_verdicts
from tests.conftest import CN, future_kickoff, today_cn


def _seed_two_matches(db):
    db.merge(SPMatch(match_id="2042501", match_no="周三012", league="英超",
                     home_raw="曼城", away_raw="布莱顿", home="曼城", away="布莱顿",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPMatch(match_id="2042502", match_no="周三001", league="英超",
                     home_raw="利物浦", away_raw="埃弗顿", home="利物浦", away="埃弗顿",
                     kickoff=future_kickoff(today_cn(), 23, 0), single_flag=True))
    cn_t = today_cn() + "T12:00:00+08:00"
    db.merge(SPSnapshot(match_id="2042501", pool="had", goal_line="",
                        sp_h=1.53, sp_d=4.40, sp_a=5.60, captured_at=cn_t))
    db.merge(SPSnapshot(match_id="2042502", pool="had", goal_line="",
                        sp_h=1.20, sp_d=4.50, sp_a=9.00, captured_at=cn_t))
    db.commit()


def _manual_user(db) -> User:
    user, _ = login_device(db, None)
    v = Verdict(
        id="v-catalog-test", trade_date=today_cn(), match_id="2042501",
        match_no="周三012", league="英超", home="曼城", away="布莱顿",
        kickoff=future_kickoff(today_cn()), pool="had", goal_line="",
        sp_h=1.53, sp_d=4.40, sp_a=5.60, rake=0.0561,
        p_home=0.61, p_draw=0.23, p_away=0.16,
        pick={"dir": "home", "sp": 1.53, "prob": 0.61},
        status="promoted", gates={"price": {"result": "pass"},
                                  "market": {"result": "pass"},
                                  "model": {"result": "pass"}},
        payload={"generated_at": "2026-11-03 19:02:00"},
        payload_hash="a" * 64,
    )
    db.add(v)
    db.add(Bet(user_id=user.id, verdict_id=v.id, amount=100, sp=1.53, pick_dir="home"))
    db.commit()
    return user


def test_matches_today_cost_evidence_avoid_water(client, db):
    _seed_two_matches(db)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    date = today_cn()

    r = client.get("/matches", params={"date": date})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and len(body["matches"]) == 2
    assert body["matches"][0]["kickoff"] <= body["matches"][1]["kickoff"]

    today = client.get("/verdicts/today", params={"date": date})
    assert today.status_code == 200
    assert today.json()["stats"]["total"] == 2
    assert len(today.json()["items"]) == 2

    cost = client.get("/matches/2042501/cost")
    assert cost.status_code == 200
    c = cost.json()
    assert c["pool"] == "had"
    assert abs(c["rake"] - 0.0595) < 0.001
    assert abs(c["cost_per_100"] - 5.61) < 0.02
    assert abs(sum(c["fair_probs"].values()) - 1.0) < 1e-5
    assert c["ev_per_100"]["h"] < 0

    ev = client.get("/matches/2042501/evidence", params={"date": date})
    assert ev.status_code == 200
    assert ev.json()["verdict_id"].startswith("v")

    avoid = client.get("/avoid-list", params={"date": date})
    assert avoid.status_code == 200
    assert avoid.json()["count"] >= 1
    assert "抽水" in avoid.json()["items"][0]["why"]

    water = client.get("/water-rank", params={"date": date, "limit": 2})
    assert water.status_code == 200
    assert water.json()["count"] == 2
    assert water.json()["items"][0]["rake"] <= water.json()["items"][1]["rake"]

    cal = client.get("/calendar", params={"month": date[:7]})
    assert cal.status_code == 200
    assert len(cal.json()["days"]) >= 28
    assert cal.json()["total_matches"] >= 2


def test_sp_movements_and_sentinel(client, db):
    _seed_two_matches(db)
    db.merge(SPSnapshot(match_id="2042501", pool="had", goal_line="",
                        sp_h=1.48, sp_d=4.50, sp_a=5.80,
                        captured_at=today_cn() + "T13:00:00+08:00"))
    db.add(Event(type="close_soon", severity=2, match_id="2042501",
                 dedupe_key="catalog-sentinel", payload={"minutes": 30},
                 data_cutoff=today_cn() + " 18:00:00"))
    db.commit()

    moves = client.get("/sp/movements", params={"date": today_cn()})
    assert moves.status_code == 200
    item = next(x for x in moves.json()["items"] if x["match_id"] == "2042501")
    assert item["prev_sp"]["h"] == 1.53
    assert item["delta"]["h"] == -0.05

    feed = client.get("/agents/sentinel/feed")
    assert feed.status_code == 200
    assert any(x["type"] == "close_soon" for x in feed.json()["items"])


def test_match_live_finished_result(client, db):
    _seed_two_matches(db)
    db.add(MatchResult(source="test", league="英超", home="曼城", away="布莱顿",
                       match_date=today_cn(), goals_home=2, goals_away=1,
                       retrieved_at=today_cn() + "T23:00:00"))
    db.commit()
    r = client.get("/matches/2042501/live")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "finished" and body["score"] == "2-1"
    assert body["live_feed"] is False  # 不伪造实时事件源
    assert body["timeline"]


def test_comfort_export_and_compat_aliases(client, db):
    _seed_two_matches(db)
    user = _manual_user(db)
    auth = {"Authorization": f"Bearer {user.device_token}"}

    comfort = client.get("/me/comfort", headers=auth)
    assert comfort.status_code == 200
    assert comfort.json()["available"] is True
    assert comfort.json()["kind"] == "pending"

    follow = client.post("/matches/2042501/follow", headers=auth, json={"events": ["final"]})
    assert follow.status_code == 200 and follow.json()["home"] == "曼城"
    assert client.delete("/matches/2042501/follow", headers=auth).status_code == 200

    assert client.patch("/me/persona", headers=auth, json={"persona": "laopao"}).status_code == 200
    assert client.post("/memories", headers=auth,
                       json={"key": "偏好", "value": "只看英超"}).status_code == 200
    assert len(client.get("/memories", headers=auth).json()) == 1
    assert client.delete("/memories/偏好", headers=auth).status_code == 200

    assert client.post("/devices", headers=auth,
                       json={"platform": "android", "provider": "jpush",
                             "token": "catalog-token"}).status_code == 200
    health = client.get("/push/health", headers=auth).json()
    assert health["total_tokens"] == 1 and health["provider"] == "jpush"
    prefs = client.get("/push/preferences", headers=auth)
    assert prefs.status_code == 200 and prefs.json()["channels"]
    assert client.put("/push/preferences", headers=auth,
                      json={"paused": True}).json()["paused"] is True
    assert client.post("/push/preferences", headers=auth,
                       json={"paused": False}).json()["paused"] is False
    assert client.patch("/me/discipline", headers=auth,
                        json={"enabled": False}).status_code == 200

    db.add(Notification(user_id=user.id, event_id=99, channel="inapp",
                        status="sent", title="提醒", body="测试",
                        created_at=datetime.now(CN).replace(tzinfo=None)))
    db.commit()
    export = client.get("/me/export", headers=auth)
    assert export.status_code == 200
    data = export.json()
    for key in ("watch_targets", "notifications", "notify_settings", "push_tokens",
                "user_events", "memories", "bets", "shares"):
        assert key in data
    assert "token" not in data["push_tokens"][0]  # 推送凭证不导出
    assert data["bets"][0]["sp"] == 1.53


def test_weekly_report_rejects_deleted_account(client, db):
    user = _manual_user(db)
    user.deleted_at = datetime.now(CN).replace(tzinfo=None)
    db.commit()
    r = client.get("/weekly-report", headers={"Authorization": f"Bearer {user.device_token}"})
    assert r.status_code == 410


def test_share_card_unified_alias(client, db):
    _seed_two_matches(db)
    build_verdicts(db, today_cn(), "2026-11-03 19:02:00")
    verdict_id = client.get("/verdicts/today", params={"date": today_cn()}).json()["items"][0]["id"]
    r = client.post("/share/card", json={"kind": "verdict", "verdict_id": verdict_id})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "verdict" and len(body["share_id"]) == 12
    assert client.post("/share/card", json={"kind": "nope"}).status_code == 422


def test_verdict_react_compat_actions(client, db):
    _seed_two_matches(db)
    user = _manual_user(db)
    auth = {"Authorization": f"Bearer {user.device_token}"}
    v = Verdict(
        id="v-react-test", trade_date=today_cn(), match_id="2042502",
        match_no="周三001", league="英超", home="利物浦", away="埃弗顿",
        kickoff=future_kickoff(today_cn(), 23, 0), pool="had", goal_line="",
        sp_h=1.20, sp_d=4.50, sp_a=9.00, rake=0.1429,
        p_home=0.78, p_draw=0.14, p_away=0.08,
        pick={"dir": "home", "sp": 1.20, "prob": 0.78},
        status="promoted", gates={"price": {"result": "pass"}},
        payload={"generated_at": "2026-11-03 19:02:00"},
        payload_hash="b" * 64,
    )
    db.add(v)
    db.commit()

    r = client.post("/verdicts/v-react-test/react", headers=auth,
                    json={"action": "bet", "amount": 50})
    assert r.status_code == 200 and r.json()["bet_id"]
    w = client.post("/verdicts/v-react-test/react", headers=auth,
                    json={"action": "watch", "events": ["final"]})
    assert w.status_code == 200 and w.json()["watch_id"]
    d = client.post("/verdicts/v-react-test/react", headers=auth,
                    json={"action": "disagree"})
    assert d.status_code == 200 and d.json()["recorded"] is True
    assert client.post("/verdicts/v-react-test/react", headers=auth,
                       json={"action": "nope"}).status_code == 422
