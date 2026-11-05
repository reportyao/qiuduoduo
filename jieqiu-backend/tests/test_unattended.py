"""未采纳复盘：看过未记注的已结算场次，只在本人 stream 返回。"""
from datetime import datetime, timezone

from app.models import Bet, InteractionEvent, SPMatch, Verdict
from tests.conftest import future_kickoff, today_cn


def _login(client, token="unattended-1"):
    body = client.post("/auth/device", json={"device_token": token}).json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user_id"]


def _verdict(db, mid="unatt-1", settled="win"):
    db.merge(SPMatch(match_id=mid, match_no="周四991", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(Verdict(
        id=f"v-{mid}", trade_date=today_cn(), match_id=mid, match_no="周四991",
        league="英超", home="曼城", away="曼联",
        kickoff=future_kickoff(today_cn()), pool="had", goal_line="",
        sp_h=1.80, sp_d=3.50, sp_a=4.20, rake=0.121,
        p_home=0.52, p_draw=0.27, p_away=0.21,
        model_h=0.56, model_d=0.24, model_a=0.20,
        pick={"dir": "主胜", "prob": 0.56, "sp": 1.80},
        rake_threshold=0.13, status="promoted", settled=settled,
        settled_at=datetime.now(timezone.utc).replace(tzinfo=None),
        result_score="2-1",
        gates={"price": {"result": "pass"}, "market": {"result": "pass"},
               "model": {"result": "pass"}},
        payload={"data_cutoff": today_cn() + "T12:00:00+08:00",
                 "model": {"engine": "test"}},
        payload_hash="d" * 64,
        sealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()


def test_unattended_review_only_for_viewed_not_bet(client, db):
    headers, uid = _login(client)
    _verdict(db)
    db.add(InteractionEvent(user_id=uid, event="verdict_viewed", session_id="s",
                            verdict_id="v-unatt-1", match_id="unatt-1",
                            event_id="evt-unatt-1"))
    db.commit()

    data = client.get("/stream", params={"date": today_cn()}, headers=headers).json()
    items = data.get("unattended") or []
    assert any(x["verdict_id"] == "v-unatt-1" for x in items)

    db.add(Bet(user_id=uid, verdict_id="v-unatt-1", amount=10,
               pick_dir="主胜"))
    db.commit()
    data = client.get("/stream", params={"date": today_cn()}, headers=headers).json()
    assert all(x["verdict_id"] != "v-unatt-1" for x in data.get("unattended") or [])
