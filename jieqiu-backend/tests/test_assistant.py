"""AI 助理运行时：事件 → 扇出 → 站内信/推送 → 设置/幂等。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.features.assistant.events import emit_event
from app.features.assistant.fanout import fanout_events
from app.features.assistant.monitors import (scan_close_soon, scan_daily_brief,
                                    scan_verdict_changes)
from app.features.assistant.worker import send_pending_push
from app.models import (Notification, PushToken, SPMatch, User, Verdict,
                        VerdictRevision, WatchTarget)
from tests.conftest import CN, future_kickoff, today_cn


def _login(client):
    r = client.post("/auth/device", json={"device_token": "assistant-test-device"})
    assert r.status_code == 200, r.text
    b = r.json()
    return b["user_id"], {"Authorization": "Bearer " + b["token"]}


def _match(db, mid="990001", no="周三901"):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="曼城", away_raw="布莱顿", home="曼城", away="布莱顿",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.commit()


def _verdict(db, vid="v-test-901", mid="990001", status="promoted"):
    v = db.get(Verdict, vid)
    if v is None:
        v = Verdict(id=vid, trade_date=today_cn(), match_id=mid, match_no="周三901",
                    league="英超", home="曼城", away="布莱顿",
                    kickoff=future_kickoff(today_cn()), pool="had", goal_line="",
                    sp_h=1.6, sp_d=4.0, sp_a=6.0, rake=0.09,
                    p_home=0.54, p_draw=0.25, p_away=0.21,
                    model_h=0.54, model_d=0.25, model_a=0.21,
                    pick={"dir": "主胜", "sp": 1.6, "ev": 0.0, "prob": 0.54},
                    status=status, gates={"price": {"result": "pass"},
                                          "market": {"result": "pass"},
                                          "model": {"result": "pass"}},
                    payload={}, payload_hash="c" * 64)
        db.add(v)
        db.commit()
    return v


def _revision(db, vid, payload, h):
    r = VerdictRevision(verdict_id=vid, payload=payload, payload_hash=h,
                        data_cutoff="2026-11-03T19:30:00+08:00")
    db.add(r)
    db.commit()
    return r


def test_verdict_monitor_only_real_change(db):
    _verdict(db, status="promoted")
    _revision(db, "v-test-901", {"status": "screening", "pick": None,
                                 "model": {"shrunk": [0.50, 0.27, 0.23]}}, "a" * 64)
    _revision(db, "v-test-901", {"status": "promoted",
                                 "pick": {"dir": "主胜", "prob": 0.54},
                                 "model": {"shrunk": [0.54, 0.25, 0.21]}}, "b" * 64)
    assert scan_verdict_changes(db, backfill=True) == 1
    assert scan_verdict_changes(db) == 0  # 游标生效，不重复


def test_close_and_daily_events_are_idempotent(db):
    now = datetime(2026, 11, 3, 20, 0, tzinfo=CN)
    db.merge(SPMatch(match_id="990002", match_no="周三902", league="英超",
                     home_raw="阿森纳", away_raw="热刺", home="阿森纳", away="热刺",
                     kickoff="2026-11-03 20:05:00", single_flag=True))
    db.commit()
    assert scan_close_soon(db, now_cn=now) == 1
    assert scan_close_soon(db, now_cn=now) == 0
    assert scan_daily_brief(db, now_cn=now) == 1
    assert scan_daily_brief(db, now_cn=now) == 0


def test_watch_fanout_inbox_and_push_dryrun(db, client):
    uid, h = _login(client)
    _match(db)
    r = client.post("/me/watch", headers=h, json={"target_type": "match",
                                                  "target_id": "990001"})
    assert r.status_code == 200, r.text
    r = client.post("/push/register", headers=h, json={
        "platform": "android", "provider": "jpush", "token": "reg-test-1"})
    assert r.status_code == 200, r.text
    _verdict(db, status="promoted")
    ev, created = emit_event(db, type="verdict_promoted", dedupe_key="test:event:1",
                             severity=2, match_id="990001",
                             payload={"verdict_id": "v-test-901", "match_id": "990001",
                                      "match_no": "周三901", "home": "曼城",
                                      "away": "布莱顿", "status": "promoted",
                                      "pick": {"dir": "主胜", "prob": 0.54}})
    assert created
    now = datetime(2026, 11, 3, 12, 0, tzinfo=CN)
    out = fanout_events(db, now_cn=now)
    assert out["inapp"] == 1 and out["push"] == 1
    # 幂等：再跑一遍不新增
    assert fanout_events(db, now_cn=now)["inapp"] == 0
    inbox = client.get("/me/inbox", headers=h).json()
    assert inbox["unread"] == 1 and len(inbox["items"]) == 1
    nid = inbox["items"][0]["id"]
    assert client.post(f"/me/inbox/{nid}/read", headers=h).status_code == 200
    assert client.get("/me/inbox/unread-count", headers=h).json()["unread"] == 0
    # JPush 未配置 → dry-run 成功
    push = db.query(Notification).filter(Notification.channel == "push").one()
    assert send_pending_push(db)["sent"] == 1
    db.refresh(push)
    assert push.status == "sent" and push.provider_msg_id.startswith("dryrun:")


def test_notify_settings_and_quiet_cap(db, client):
    uid, h = _login(client)
    _match(db)
    client.post("/me/watch", headers=h, json={"target_type": "match", "target_id": "990001"})
    client.post("/push/register", headers=h, json={
        "platform": "android", "provider": "jpush", "token": "reg-test-2"})
    r = client.put("/me/notify-settings", headers=h, json={
        "channels": ["inapp", "push"], "quiet_start": "23:30", "quiet_end": "08:00",
        "daily_cap": 0})
    assert r.status_code == 200
    emit_event(db, type="close_soon", dedupe_key="test:event:quiet", severity=2,
               match_id="990001",
               payload={"match_id": "990001", "home": "曼城", "away": "布莱顿",
                        "minutes": 5})
    out = fanout_events(db, now_cn=datetime(2026, 11, 3, 23, 45, tzinfo=CN))
    assert out["inapp"] == 1 and out["push"] == 0
    push = db.query(Notification).filter(Notification.channel == "push").one()
    assert push.status == "suppressed" and push.last_error in ("daily_cap", "quiet_hours")


def test_push_register_rejects_ios(db, client):
    uid, h = _login(client)
    r = client.post("/push/register", headers=h, json={
        "platform": "ios", "provider": "jpush", "token": "x"})
    assert r.status_code == 422


def test_console_assistant_and_push_pages(db, client):
    r = client.post("/console/login", data={"pw": "dev"}, follow_redirects=False)
    assert r.status_code == 302
    tok = r.headers["location"].split("t=")[1]
    assert client.get(f"/console/assistant?t={tok}").status_code == 200
    assert client.get(f"/console/push?t={tok}").status_code == 200


def test_purge_removes_assistant_data(db):
    from datetime import datetime, timedelta, timezone
    from app.models import NotifySettings, UserEvent
    from app.modules.users import login_device, purge_expired_deletions

    user, _ = login_device(db, "tok-assistant-purge")
    user.deleted_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.add(WatchTarget(user_id=user.id, target_type="match", target_id="990001"))
    db.add(PushToken(user_id=user.id, provider="jpush", token="purge-token"))
    db.add(NotifySettings(user_id=user.id))
    db.add(Notification(user_id=user.id, event_id=1, channel="inapp", status="sent"))
    db.add(UserEvent(user_id=user.id, kind="view", target_id="990001"))
    db.commit()
    counts = purge_expired_deletions(db, days=7)
    assert counts["purged_users"] == 1
    assert counts["removed_watches"] == 1
    assert counts["removed_push_tokens"] == 1
    assert counts["removed_notifications"] == 1
    assert counts["removed_notify_settings"] == 1
    assert counts["removed_user_events"] == 1
    assert not db.query(WatchTarget).filter(WatchTarget.user_id == user.id).all()


def test_scan_settlements_recent_utc(db):
    from datetime import datetime, timezone
    from app.features.assistant.monitors import scan_settlements
    v = _verdict(db, vid="v-test-settle", mid="990001")
    v.settled = "win"
    v.settled_at = datetime.now(timezone.utc)
    v.result_score = "2-0"
    db.commit()
    now_cn = datetime.now(CN)
    assert scan_settlements(db, now_cn=now_cn) == 1
    assert scan_settlements(db, now_cn=now_cn) == 0
