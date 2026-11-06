"""采集器心跳与后台远程重启。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import CollectorStatus
from tests.conftest import admin_login


def _heartbeat(client, started_at="2026-11-06T08:00:00+00:00"):
    return client.post("/collector/heartbeat", json={
        "host": "home-pc", "pid": "123", "version": "v0.2",
        "started_at": started_at,
        "last_success_at": "2026-11-06T08:05:00+08:00",
        "last_error": "", "cycle": 3, "matches": 14,
        "snapshots_total": 100, "last_push_at": "2026-11-06T08:00:00+08:00",
    }, headers={"Authorization": "Bearer test-collector-token"})


def test_heartbeat_requires_configured_token(client, monkeypatch):
    from app.routers import collector as collector_router
    monkeypatch.setattr(collector_router, "get_settings",
                        lambda: type("S", (), {"collector_token": ""})())
    assert _heartbeat(client).status_code == 503


def test_heartbeat_rejects_bad_token(client, monkeypatch):
    from app.routers import collector as collector_router
    monkeypatch.setattr(collector_router, "get_settings",
                        lambda: type("S", (), {"collector_token": "right"})())
    response = client.post("/collector/heartbeat", json={
        "host": "x", "pid": "1", "started_at": "2026-11-06T08:00:00+00:00",
    }, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_heartbeat_upserts_and_admin_restart(client, db, monkeypatch):
    from app.routers import collector as collector_router
    monkeypatch.setattr(collector_router, "get_settings",
                        lambda: type("S", (), {"collector_token": "test-collector-token"})())
    first = _heartbeat(client)
    assert first.status_code == 200
    assert first.json()["restart"] is False
    row = db.get(CollectorStatus, 1)
    assert row.host == "home-pc" and row.cycle == 3

    admin_login(client)
    status = client.get("/admin/api/collector")
    assert status.status_code == 200
    assert status.json()["state"] in ("online", "stale")

    restart = client.post("/admin/api/collector/restart")
    assert restart.status_code == 200
    assert restart.json()["restart_pending"] is True

    # 旧进程心跳 → 下发重启
    again = _heartbeat(client)
    assert again.json()["restart"] is True

    # 新进程（started_at 晚于请求）心跳 → 清除指令
    new_start = datetime.now(timezone.utc).isoformat()
    cleared = _heartbeat(client, started_at=new_start)
    assert cleared.json()["restart"] is False
    db.expire_all()
    assert db.get(CollectorStatus, 1).restart_requested_at is None
