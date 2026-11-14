"""运营工作台：全链路快照 / 诊断降级 / allowlist 动作。"""
from __future__ import annotations

from app.features.ops import workbench as ops
from app.models import CollectorStatus, OpsException, OpsJob
from tests.conftest import admin_login, today_cn


def test_workbench_with_empty_data_marks_blockers(db):
    wb = ops.build_workbench(db)
    assert wb["date"] == today_cn()
    assert wb["overall"] in ("blocked", "warn")
    keys = {s["key"] for s in wb["stages"]}
    assert {"collect", "ingest", "intel", "market", "model", "gates", "seal",
            "review", "publish", "llm", "push"} <= keys
    for stage in wb["stages"]:
        assert isinstance(stage["evidence"], list), stage["key"]
        assert isinstance(stage["next"], str), stage["key"]
    assert "SP" in wb["definitions"]
    assert any(s["key"] == "collect" and s["state"] == "blocked"
               for s in wb["stages"])


def test_workbench_diagnose_falls_back_without_deep_key(db):
    result = ops.diagnose_workbench(db)
    assert result["diagnosis"]["fallback"] is True
    assert result["diagnosis"]["needs_human"]


def test_workbench_restart_action_requires_collector(db, monkeypatch):
    result = ops.run_action(db, "restart_collector")
    assert result["ok"] is False
    db.add(CollectorStatus(id=1, host="home", pid="1", last_seen=ops._utcnow()))
    db.commit()
    result = ops.run_action(db, "restart_collector")
    assert result["ok"] is True
    db.expire_all()
    assert db.get(CollectorStatus, 1).restart_requested_at is not None


def test_workbench_api_requires_login(client):
    assert client.get("/admin/api/workbench").status_code == 401


def test_workbench_api_with_admin(client):
    admin_login(client)
    response = client.get("/admin/api/workbench")
    assert response.status_code == 200
    assert "stages" in response.json()


def test_workbench_ops_stage_reflects_health(db):
    """OPC 阶段：无异常时 ok；核心任务失败/严重异常时 blocked。"""
    wb = ops.build_workbench(db)
    stage = next(s for s in wb["stages"] if s["key"] == "ops")
    assert stage["state"] == "ok"
    assert "监控任务" in stage["headline"] or "任务运行记录" in stage["headline"]
    assert wb["raw"]["ops"]["open_exceptions"] == 0

    # 核心任务最近失败 → blocked
    import datetime as dt
    db.add(OpsJob(job_key="settle_pending", status="error",
                  started_at=dt.datetime(2026, 11, 14, 6, 0),
                  error="boom"))
    db.add(OpsException(type="settlement_error", severity=3,
                        message="crash", status="open",
                        dedupe_key="test-sev3"))
    db.commit()
    wb2 = ops.build_workbench(db)
    stage2 = next(s for s in wb2["stages"] if s["key"] == "ops")
    assert stage2["state"] == "blocked"
    assert "settle_pending" in stage2["headline"]
    assert wb2["raw"]["ops"]["open_exceptions"] >= 1


def test_run_action_crash_records_error_exception(db, monkeypatch):
    """OPC：动作内部崩溃（非业务失败）→ job error + sev3 异常 + 异常继续抛。"""
    from app.modules import ops as ops_module
    from app.models import OpsException

    def boom(db, action, date):
        raise RuntimeError("net down")
    monkeypatch.setattr(ops, "_run_action_impl", boom)
    import pytest
    with pytest.raises(RuntimeError):
        ops.run_action(db, "sync_intel", date="2026-11-14")
    job = (db.query(OpsJob)
           .filter(OpsJob.job_key == "action_sync_intel")
           .order_by(OpsJob.id.desc()).first())
    assert job is not None and job.status == "error"
    assert "RuntimeError" in (job.error or "")
    exc = (db.query(OpsException)
           .filter(OpsException.dedupe_key == "action_sync_intel_error")
           .first())
    assert exc is not None and int(exc.severity) == 3


def test_run_action_records_ops_job(db):
    """管理员一键动作必须写 ops_jobs：业务失败记 error + sev2 异常。"""
    result = ops.run_action(db, "sync_sportmonks", date="2026-11-14")
    job = (db.query(OpsJob)
           .filter(OpsJob.job_key == "action_sync_sportmonks")
           .order_by(OpsJob.id.desc()).first())
    assert job is not None, "动作必须记录 ops_job"
    # 无 sportmonks 数据的测试库：业务失败（ok False → error）或成功（ok）
    assert job.status in ("ok", "error")
    assert job.status == ("ok" if result.get("ok") else "error")
    if not result.get("ok"):
        exc = (db.query(OpsException)
               .filter(OpsException.dedupe_key == "action_sync_sportmonks_fail")
               .first())
        assert exc is not None
        assert exc.status == "open"
