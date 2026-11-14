"""管理后台 v4：用户手动开通、AI 计划、OPC、引擎配置。"""
from __future__ import annotations

from app.models import AnalysisQuota, OpsJob, User
from app.modules.membership import expire_all
from app.modules.plan_service import settle_open_cycles
from app.modules.timeutil import trade_date_now
from tests.conftest import admin_login


def test_admin_shell_has_v4_views(client):
    html = client.get("/admin").text
    assert "用户与会员" in html
    assert "异常队列" in html
    assert "AI 计划" in html
    assert 'id="view-app-users"' in html
    assert 'id="view-ops-v4"' in html


def test_workbench_collector_unknown_age_copy(client):
    admin_login(client)
    payload = client.get("/admin/api/workbench")
    assert payload.status_code == 200
    text = payload.text
    assert "未知前更新" not in text
    collect = next(stage for stage in payload.json()["stages"]
                   if stage["key"] == "collect")
    assert "SP 文件" in collect["headline"]


def test_admin_app_user_membership_and_masking(client, db):
    user = User(id="u-admin-v4", device_token="dev-admin-v4",
                display_name="后台测试", phone="13800138000",
                email="v4@example.com")
    db.add(user)
    db.commit()
    admin_login(client)

    listed = client.get("/admin/api/app-users?query=13800138000")
    assert listed.status_code == 200
    row = next(x for x in listed.json()["users"] if x["user_id"] == user.id)
    assert row["phone"] != "13800138000"
    assert "****" in row["phone"]
    assert row["membership"]["tier"] == "free"

    granted = client.post(f"/admin/api/app-users/{user.id}/membership",
                          json={"tier": "max", "days": 30, "note": "test"})
    assert granted.status_code == 200
    assert granted.json()["membership"]["tier"] == "max"

    revoked = client.post(f"/admin/api/app-users/{user.id}/membership/revoke",
                          json={"note": "test revoke"})
    assert revoked.status_code == 200
    assert revoked.json()["membership"]["tier"] == "free"


def test_admin_engine_config_and_ops(client):
    admin_login(client)
    got = client.get("/admin/api/engine-config")
    assert got.status_code == 200
    assert got.json()["version"] == "V3.21"

    updated = client.put("/admin/api/engine-config", json={
        "version": "V3.22", "markets_monitored": 5,
        "models_reviewing": 7, "data_points_factor": 6,
    })
    assert updated.status_code == 200
    assert updated.json()["config"]["version"] == "V3.22"

    ops = client.get("/admin/api/ops-v4")
    assert ops.status_code == 200
    assert "jobs" in ops.json() and "exceptions" in ops.json()


def test_admin_plans_endpoint(client):
    admin_login(client)
    response = client.get("/admin/api/plans?risk=stable&limit=5")
    assert response.status_code == 200
    assert "plans" in response.json()


def test_ops_v4_job_summary(client, db):
    """OPC：/api/ops-v4 返回按 job_key 聚合的健康汇总。"""
    import datetime as dt
    db.add(OpsJob(job_key="settle_pending", status="ok",
                  started_at=dt.datetime(2026, 11, 14, 6, 0)))
    db.commit()
    admin_login(client)
    payload = client.get("/admin/api/ops-v4?limit=80")
    assert payload.status_code == 200
    body = payload.json()
    assert isinstance(body.get("summary"), list)
    row = next(x for x in body["summary"] if x["job_key"] == "settle_pending")
    assert row["runs"] >= 1
    assert row["errors"] == 0
    assert row["last_status"] == "ok"


def test_ops_producers_write_jobs(db):
    """OPC 生产者：settle_open_cycles 与 membership.expire_all 必须写 ops_jobs。"""
    before = {j.job_key for j in db.query(OpsJob).all()}
    assert settle_open_cycles(db) == 0
    assert expire_all(db) == 0
    after = {j.job_key for j in db.query(OpsJob).all()}
    assert "settle_open_cycles" in after
    assert "membership_expire" in after
    fresh = [j for j in db.query(OpsJob).all()
             if j.job_key in ("settle_open_cycles", "membership_expire")
             and j.job_key not in before]
    assert all(j.status == "ok" for j in fresh)


def test_admin_app_users_compliance_quota(client, db):
    """app-users 与前端能力对齐：合规/保护/今日额度字段。"""
    user = User(id="u-opc-compliance", device_token="dev-opc-compliance",
                display_name="合规巡检", age_verified=False,
                under18_locked=False, discipline_on=False,
                rested_until="2026-11-20")
    db.add(user)
    db.add(AnalysisQuota(user_id=user.id, trade_date=trade_date_now(),
                         limit_count=3, used=2))
    db.commit()
    admin_login(client)
    listed = client.get("/admin/api/app-users?query=u-opc-compliance")
    assert listed.status_code == 200
    row = next(x for x in listed.json()["users"] if x["user_id"] == user.id)
    assert row["age_verified"] is False
    assert row["discipline_on"] is False
    assert row["rested_until"] == "2026-11-20"
    assert row["quota"]["used"] == 2
    assert row["quota"]["limit"] == 3
