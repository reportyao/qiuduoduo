"""新版管理后台 UI/API。"""
from __future__ import annotations

from app.models import PersonaLLMModel
from tests.conftest import admin_login, today_cn


def login(client, username: str = "admin", password: str = "dev"):
    return admin_login(client, username, password).json()


def test_admin_shell_public_and_api_requires_auth(client):
    shell = client.get("/admin")
    assert shell.status_code == 200
    assert "球多多运营台" in shell.text
    assert client.get("/admin/api/overview").status_code == 401
    assert client.get("/admin/assets/admin.js").status_code == 200


def test_admin_asset_whitelist_rejects_other_files(client):
    assert client.get("/admin/assets/admin.css").status_code == 200
    # 白名单之外的文件 / 路径穿越一律 404
    assert client.get("/admin/assets/index.html").status_code == 404
    assert client.get("/admin/assets/..%2Fconfig.py").status_code == 404
    assert client.get("/admin/assets/nope.js").status_code == 404


def test_admin_model_specific_test_uses_that_model(client, db, monkeypatch):
    from app.modules import persona_llm
    login(client)
    row = PersonaLLMModel(name="Single Test", base_url="https://example.invalid/v1",
                          model="single-test-model", api_key_enc="enc", priority=70)
    db.add(row)
    db.commit()

    called = {}

    def fake_call(r, text, persona, db=None):
        called["model"] = r.model
        return f"{persona}:{text[:4]}", {}, 12

    monkeypatch.setattr(persona_llm, "_call_model", fake_call)
    result = client.post(f"/admin/api/models/{row.id}/test",
                         json={"persona": "laopao", "text": "今天主看曼城。"})
    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is True
    assert body["model"] == "single-test-model"
    assert called["model"] == "single-test-model"
    assert body["latency_ms"] == 12


def test_admin_overview_and_models_crud(client, db):
    login(client)
    overview = client.get("/admin/api/overview")
    assert overview.status_code == 200
    data = overview.json()
    assert data["date"] == today_cn()
    assert data["counts"]["models"]["total"] >= 2

    payload = {
        "name": "Admin Test", "base_url": "https://example.invalid/v1",
        "model": "admin-test-model", "api_key": "sk-secret-123",
        "priority": 55, "max_tokens": 300, "temperature": 0.2,
    }
    created = client.post("/admin/api/models", json=payload)
    assert created.status_code == 200, created.text
    row = created.json()["model"]
    assert row["key"] == "已配置"
    assert row["priority"] == 55
    db_row = db.get(PersonaLLMModel, row["id"])
    assert "sk-secret" not in db_row.api_key_enc

    patched = client.patch(f"/admin/api/models/{row['id']}", json={
        "priority": 5, "enabled": False, "reset_failures": True,
    })
    assert patched.status_code == 200
    assert patched.json()["model"]["priority"] == 5
    assert patched.json()["model"]["enabled"] is False

    deleted = client.delete(f"/admin/api/models/{row['id']}")
    assert deleted.status_code == 200
    assert db.get(PersonaLLMModel, row["id"]) is None


def test_admin_model_key_is_not_returned(client, db):
    login(client)
    row = PersonaLLMModel(name="Key Test", base_url="https://example.invalid/v1",
                          model="key-test", api_key_enc="enc", priority=80)
    db.add(row)
    db.commit()
    result = client.post(f"/admin/api/models/{row.id}/key", json={"api_key": "sk-new-value"})
    assert result.status_code == 200
    assert result.json()["model"]["key"] == "已配置"
    assert "sk-new-value" not in result.text


def test_admin_personas_update(client, db):
    login(client)
    data = client.get("/admin/api/personas").json()
    assert {p["id"] for p in data["profiles"]} >= {"zhuanjia", "laopao", "meng"}
    updated = client.put("/admin/api/personas/laopao", json={
        "address": "老铁", "tone": "老铁 · 直接", "max_chars": 180,
        "style_prompt": "短句，直接。",
    })
    assert updated.status_code == 200
    slot = client.put("/admin/api/personas/laopao/slots/today_pick", json={
        "template": "老铁，今天看 {home} vs {away}。", "enabled": True,
    })
    assert slot.status_code == 200
    profiles = client.get("/admin/api/personas").json()["profiles"]
    row = next(p for p in profiles if p["id"] == "laopao")
    assert row["address"] == "老铁"
    assert row["max_chars"] == 180


def test_admin_recommendations_read_and_empty_pipeline(client, db):
    login(client)
    data = client.get("/admin/api/recommendations?limit=1").json()
    assert data["date"] == today_cn()
    assert isinstance(data["snapshots"], list)
    assert data["page"]["limit"] == 1
    assert "has_more" in data["page"]
    result = client.post("/admin/api/recommendations/run", json={"stake": 100})
    assert result.status_code == 200
    assert {"snapshots", "plans", "reviewed", "published"} <= set(result.json())


def test_admin_gateway_data_logs(client, db):
    login(client)
    gateway = client.get("/admin/api/gateway").json()
    assert "profiles" in gateway and "routes" in gateway
    data = client.get("/admin/api/data").json()
    assert data["verdicts"]["total"] >= 0
    assert "sync" in data
    logs = client.get("/admin/api/logs?name=sync&lines=20")
    assert logs.status_code == 200
    assert isinstance(logs.json()["lines"], list)
    assert client.get("/admin/api/logs?name=not-allowed").status_code == 404


def test_admin_overview_actions_and_batch(client, db):
    login(client)
    overview = client.get("/admin/api/overview").json()
    assert "actions" in overview
    assert "sync" in overview
    assert isinstance(overview["actions"], list)
    ops = client.get("/admin/api/ops")
    assert ops.status_code == 200
    assert "alerts" in ops.json()

    bad = client.get("/admin/api/recommendations?date=not-a-date")
    assert bad.status_code == 400
    bad = client.post("/admin/api/recommendations/run", json={"date": "2026-13-40"})
    assert bad.status_code == 400

    review = client.post("/admin/api/recommendations/batch",
                         json={"action": "review", "date": today_cn()})
    assert review.status_code == 200
    assert review.json()["action"] == "review"
    publish = client.post("/admin/api/recommendations/batch",
                          json={"action": "publish", "date": today_cn()})
    assert publish.status_code == 200
    assert "done" in publish.json()


def test_admin_rbac_and_audit_log(client, db):
    login(client)
    created = client.post("/admin/api/users", json={
        "username": "viewer1", "password": "viewer-pass-123", "role": "viewer",
    })
    assert created.status_code == 200, created.text
    assert created.json()["user"]["role"] == "viewer"

    # 切到 viewer：读可以，写必须 403
    client.post("/admin/api/logout")
    login(client, "viewer1", "viewer-pass-123")
    assert client.get("/admin/api/overview").status_code == 200
    denied = client.post("/admin/api/models", json={
        "name": "Denied", "base_url": "https://example.invalid/v1",
        "model": "denied-model",
    })
    assert denied.status_code == 403

    # 切回 admin：审计里能看到用户创建
    client.post("/admin/api/logout")
    login(client)
    audit = client.get("/admin/api/audit").json()
    assert audit["total"] >= 1
    assert any(item["action"] == "user.create" for item in audit["items"])
    assert "password" not in str(audit["items"]).lower()


def test_admin_login_lockout(client):
    from app.modules import admin_auth as A
    A._LOGIN_FAILS.clear()
    try:
        for _ in range(5):
            r = client.post("/admin/api/login", json={
                "username": "admin", "password": "wrong-pass"})
            assert r.status_code == 401
        r = client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong-pass"})
        assert r.status_code == 429 and r.headers.get("retry-after") == "600"
    finally:
        A._LOGIN_FAILS.clear()


def test_admin_write_requires_csrf(client):
    login(client)
    client.headers.pop("x-csrf-token", None)
    denied = client.post("/admin/api/recommendations/run", json={"stake": 100})
    assert denied.status_code == 403
    assert "CSRF" in denied.text
    # GET 不受影响
    assert client.get("/admin/api/overview").status_code == 200


def test_role_change_revokes_sessions(db):
    from app.modules import admin_auth as A
    user = A.create_user(db, "revoke-me", "password-123", "operator")
    token, _ = A.create_session(user)
    assert token in A._SESSIONS
    assert A.revoke_all_for_user(user.id) >= 1
    assert token not in A._SESSIONS


def test_admin_data_exposes_football_coverage(client, db):
    login(client)
    af = client.get("/admin/api/data").json()["api_football"]
    assert "target" in af and "warnings" in af
    assert {"matches", "linked", "lineups", "injuries"} <= set(af["target"])
    assert isinstance(af["warnings"], list)
