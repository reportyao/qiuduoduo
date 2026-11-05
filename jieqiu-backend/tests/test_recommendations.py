"""推荐主链：snapshot → review → publish → expire/withdraw。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.features.recommendations import service
from app.models import (DecisionSnapshot, RecommendationEvent, ReviewRun, SPMatch,
                       SPSnapshot, Verdict)
from tests.conftest import admin_login, future_kickoff, today_cn


def _seed_market(db, mid: str, no: str):
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kick, single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=1.80, sp_d=3.50, sp_a=4.20,
                        captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()


def _seed(db, *, mid: str = "rec-1", no: str = "周三901",
          sealed: bool = True, status: str = "promoted") -> Verdict:
    kick = future_kickoff(today_cn())
    v = Verdict(
        id=f"v-{mid}", trade_date=today_cn(), match_id=mid, match_no=no,
        league="英超", home="曼城", away="曼联", kickoff=kick,
        pool="had", goal_line="", sp_h=1.80, sp_d=3.50, sp_a=4.20,
        rake=0.121, p_home=0.52, p_draw=0.27, p_away=0.21,
        model_h=0.56, model_d=0.24, model_a=0.20,
        pick={"dir": "主胜", "prob": 0.56, "sp": 1.80},
        rake_threshold=0.13, status=status,
        gates={"price": {"result": "pass"},
               "market": {"result": "pass"},
               "model": {"result": "pass"}},
        payload={"data_cutoff": today_cn() + "T12:00:00+08:00",
                 "model": {"engine": "DC v1.1"}},
        payload_hash="a" * 64,
        sealed_at=datetime.now(timezone.utc).replace(tzinfo=None) if sealed else None,
    )
    v = db.merge(v)
    db.commit()
    return v


def test_build_review_publish_and_public_today(client, db):
    _seed(db)
    snaps = service.build_snapshots(db, today_cn())
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.status == service.DRAFT
    assert snap.payload["direction"] == "主胜"
    assert snap.payload["conditions"] and snap.payload["invalidators"]
    assert snap.payload_hash

    run = service.review_subject(db, service.SUBJECT_DECISION, snap.id)
    assert run.status == "passed"
    assert snap.status == service.APPROVED
    assert snap.review_run_id == run.id

    service.publish_subject(db, service.SUBJECT_DECISION, snap.id)
    assert snap.status == service.PUBLISHED
    assert snap.published_at is not None

    data = client.get("/recommendations/today").json()
    assert data["trade_date"] == today_cn()
    assert len(data["verdicts"]) == 1
    assert data["verdicts"][0]["id"] == "v-rec-1"
    assert data["snapshots"][0]["snapshot_id"] == snap.id

    # 重复 build 不产生新版本；公开详情可读
    again = service.build_snapshots(db, today_cn())
    assert again[0].id == snap.id
    detail = client.get(f"/recommendations/{snap.id}")
    assert detail.status_code == 200
    assert detail.json()["snapshot_id"] == snap.id


def test_unsealed_cannot_publish_and_events_are_written(db):
    v = _seed(db, mid="rec-2", no="周三902", sealed=False)
    snap = service.build_snapshots(db, today_cn())[0]
    run = service.review_subject(db, service.SUBJECT_DECISION, snap.id)
    assert run.status == "failed"
    assert snap.status == service.REVIEW_FAILED
    # L5 的封存门必须命中
    assert any(layer["name"] == "L5_publish_gate" and layer["status"] == "fail"
               for layer in run.layers)
    with pytest.raises(ValueError):
        service.publish_subject(db, service.SUBJECT_DECISION, snap.id)
    assert db.query(RecommendationEvent).filter_by(action="review").count() == 1
    assert db.query(ReviewRun).count() == 1


def test_withdraw_and_expire_remove_from_public_today(client, db):
    _seed(db, mid="rec-3", no="周三903")
    snap = service.build_snapshots(db, today_cn())[0]
    service.review_subject(db, service.SUBJECT_DECISION, snap.id)
    service.publish_subject(db, service.SUBJECT_DECISION, snap.id)
    public = client.get("/recommendations/today").json()["snapshots"][0]
    assert len(client.get("/recommendations/today").json()["snapshots"]) == 1
    assert public["direction"]
    assert public["conditions"] and public["invalidators"]
    assert public["review"] and public["review"]["status"] == "passed"

    service.withdraw_subject(db, service.SUBJECT_DECISION, snap.id, "test")
    assert snap.status == service.WITHDRAWN
    assert client.get("/recommendations/today").json()["snapshots"] == []

    # 新版本发布后，旧版本源变化会被 expired；今天接口只留 published
    _seed(db, mid="rec-3", no="周三903")
    v = db.get(Verdict, "v-rec-3")
    v.payload_hash = "c" * 64
    db.commit()
    newer = service.build_snapshots(db, today_cn())[0]
    assert newer.id != snap.id
    assert newer.version == 2


def test_expire_due_hides_published_snapshot(client, db):
    _seed(db, mid="rec-4", no="周三904")
    snap = service.build_snapshots(db, today_cn())[0]
    service.review_subject(db, service.SUBJECT_DECISION, snap.id)
    service.publish_subject(db, service.SUBJECT_DECISION, snap.id)
    snap.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()
    data = client.get("/recommendations/today").json()
    assert data["snapshots"] == []
    # GET 只读：状态由 cron/流水线的 expire_due 落盘
    assert snap.status == service.PUBLISHED
    service.expire_due(db, today_cn())
    assert snap.status == service.EXPIRED


def test_build_plan_review_and_publish(client, db):
    for i in range(2):
        _seed_market(db, f"rec-plan-{i}", f"周三91{i}")
        _seed(db, mid=f"rec-plan-{i}", no=f"周三91{i}")
    plans = service.build_plans(db, today_cn(), stake=100)
    assert plans
    published = []
    for plan in plans:
        run = service.review_subject(db, service.SUBJECT_PLAN, plan.id)
        if run.status == "passed":
            service.publish_subject(db, service.SUBJECT_PLAN, plan.id)
            published.append(plan)
    assert published, [(p.status, p.review_run_id) for p in plans]
    data = client.get("/recommendations/today").json()
    assert data["plans"]
    plan = data["plans"][0]
    assert plan["risk_profile"] in ("conservative", "balanced", "aggressive")
    assert plan["conditions"] and plan["invalidators"]
    assert plan["review"] and plan["review"]["status"] == "passed"


def test_admin_recommendation_run_and_withdraw(client, db):
    _seed(db, mid="rec-console", no="周三920")
    admin_login(client)
    page = client.get("/admin/api/recommendations?date=" + today_cn())
    assert page.status_code == 200
    assert "snapshots" in page.json()
    r = client.post("/admin/api/recommendations/run", json={"date": today_cn()})
    assert r.status_code == 200, r.text
    snaps = client.get("/admin/api/recommendations?date=" + today_cn()).json()["snapshots"]
    assert any(s["match_no"] == "周三920" for s in snaps)
    snap = db.query(DecisionSnapshot).filter_by(match_id="rec-console").one()
    assert snap.status == service.PUBLISHED
    r = client.post(f"/admin/api/recommendations/decision/{snap.id}/withdraw",
                    json={"reason": "test"})
    assert r.status_code == 200, r.text
    db.refresh(snap)
    assert snap.status == service.WITHDRAWN
