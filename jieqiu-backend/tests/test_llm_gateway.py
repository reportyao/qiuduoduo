"""LLM Gateway：任务路由 / 缓存 / 预算 / 降级 / 后台。"""
from __future__ import annotations

from types import SimpleNamespace

from app.models import LLMBudget, LLMCache, LLMUsage
from app.modules import llm_gateway
from tests.conftest import admin_login


def _settings(**over):
    base = dict(
        llm_fast_provider="glm", llm_fast_base_url="https://example.invalid/v4",
        llm_fast_model="glm-4-flash", llm_fast_api_key="test-key",
        llm_fast_input_price_cny_per_m=1.0, llm_fast_output_price_cny_per_m=2.0,
        llm_deep_provider="deepseek", llm_deep_base_url="https://example.invalid/v1",
        llm_deep_model="deepseek-chat", llm_deep_api_key="",
        llm_deep_input_price_cny_per_m=2.0, llm_deep_output_price_cny_per_m=8.0,
        llm_timeout_s=5, llm_max_retries=1, llm_daily_budget_cny=10.0,
        llm_task_budget_cny=5.0, llm_user_daily_calls=50,
        llm_cache_ttl_seconds=1800,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _msgs(text="你好"):
    return [{"role": "user", "content": text}]


def test_unconfigured_profile_degrades(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings",
                        lambda: _settings(llm_fast_api_key=""))
    res = llm_gateway.complete(db, "open_chat", _msgs())
    assert res.degraded is True
    assert res.error_class == "not_configured"
    assert db.query(LLMUsage).count() == 0


def test_success_cache_and_usage(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings())
    calls = {"n": 0}

    def fake_call(profile, messages, **kw):
        calls["n"] += 1
        return "克制回答", {"input_tokens": 100, "output_tokens": 50}

    monkeypatch.setattr(llm_gateway, "_call", fake_call)
    r1 = llm_gateway.complete(db, "open_chat", _msgs(), session_id="s1")
    r2 = llm_gateway.complete(db, "open_chat", _msgs(), session_id="s1")
    assert r1.degraded is False and r1.text == "克制回答"
    assert r2.cached is True and calls["n"] == 1
    assert db.query(LLMUsage).count() == 2
    assert db.query(LLMCache).count() == 1
    assert db.query(LLMCache).first().hit_count == 1
    # 100 in * 1元/M + 50 out * 2元/M = 0.0002
    usage = db.query(LLMUsage).filter(LLMUsage.status == "ok").one()
    assert abs(usage.cost_cny - 0.0002) < 1e-9
    budget = db.query(LLMBudget).filter(LLMBudget.task == "open_chat").one()
    assert abs(budget.spent_cny - 0.0002) < 1e-9
    assert budget.reserved_cny == 0


def test_private_cache_does_not_cross_users(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings())
    monkeypatch.setattr(llm_gateway, "_call",
                        lambda *a, **k: ("ok", {"input_tokens": 1, "output_tokens": 1}))
    llm_gateway.complete(db, "open_chat", _msgs(), session_id="s1")
    llm_gateway.complete(db, "open_chat", _msgs(), session_id="s2")
    assert db.query(LLMCache).count() == 2


def test_cache_key_includes_generation_params(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings())
    calls = {"n": 0}

    def fake_call(*a, **k):
        calls["n"] += 1
        return "ok", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(llm_gateway, "_call", fake_call)
    llm_gateway.complete(db, "open_chat", _msgs(), max_tokens=100)
    llm_gateway.complete(db, "open_chat", _msgs(), max_tokens=200)
    assert calls["n"] == 2
    assert db.query(LLMCache).count() == 2


def test_pii_redacted_before_provider(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings())
    seen = {}

    def fake_call(profile, messages, **kw):
        seen["content"] = messages[-1]["content"]
        return "ok", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(llm_gateway, "_call", fake_call)
    llm_gateway.complete(db, "open_chat",
                         _msgs("联系我 13812345678 或 a@b.com"))
    assert "13812345678" not in seen["content"]
    assert "a@b.com" not in seen["content"]
    assert "[手机号]" in seen["content"] and "[邮箱]" in seen["content"]


def test_user_daily_quota_degrades(db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "_settings",
                        lambda: _settings(llm_user_daily_calls=1))
    monkeypatch.setattr(llm_gateway, "_call",
                        lambda *a, **k: ("ok", {"input_tokens": 1, "output_tokens": 1}))
    first = llm_gateway.complete(db, "open_chat", _msgs("a"), session_id="quota")
    second = llm_gateway.complete(db, "open_chat", _msgs("b"), session_id="quota")
    assert first.degraded is False
    assert second.degraded is True and second.error_class == "user_quota"
    assert db.query(LLMUsage).filter_by(status="blocked").count() == 1


def test_budget_exceeded_degrades(db, monkeypatch):
    # 输入 1 token + 输出上限 10 token 的预估成本 > 日预算
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings(
        llm_daily_budget_cny=0.000001,
        llm_task_budget_cny=0.000001,
        llm_fast_output_price_cny_per_m=100.0))
    res = llm_gateway.complete(db, "open_chat", _msgs(), max_tokens=10)
    assert res.degraded is True and res.error_class == "budget_exceeded"
    assert db.query(LLMCache).count() == 0


def _token(client):
    return client.post("/auth/device", json={}).json()["token"]


def test_chat_fallback_uses_gateway(client, db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "complete", lambda *a, **k: llm_gateway.LLMResult(
        text="这是模型回答", provider="glm", model="glm-4-flash"))
    token = _token(client)
    r = client.post("/chat", json={"text": "随便聊聊", "session_id": "s-chat"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["text"] == "这是模型回答"
    assert data["llm"]["model"] == "glm-4-flash"


def test_chat_gateway_exception_falls_back(client, db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(llm_gateway, "complete", boom)
    token = _token(client)
    r = client.post("/chat", json={"text": "随便聊聊"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "fallback"
    assert "今日预测" in data["text"]


def test_anonymous_chat_never_calls_gateway(client, db, monkeypatch):
    called = {"n": 0}

    def fake(*a, **k):
        called["n"] += 1
        return llm_gateway.LLMResult(text="不该出现")

    monkeypatch.setattr(llm_gateway, "complete", fake)
    data = client.post("/chat", json={"text": "随便聊聊"}).json()
    assert called["n"] == 0
    assert "今日预测" in data["text"]
    assert "llm" not in data


def test_chat_rejects_banned_llm_output(client, db, monkeypatch):
    monkeypatch.setattr(llm_gateway, "complete", lambda *a, **k: llm_gateway.LLMResult(
        text="这场可以稳赚", provider="glm", model="glm-4-flash"))
    token = _token(client)
    data = client.post("/chat", json={"text": "随便聊聊"},
                       headers={"Authorization": f"Bearer {token}"}).json()
    assert "稳赚" not in data["text"]
    assert data["llm"]["filtered"] == ["稳赚"]


def test_admin_gateway_status(client, db):
    admin_login(client)
    data = client.get("/admin/api/gateway").json()
    assert {p["name"] for p in data["profiles"]} == {"fast", "deep"}
    assert data["routes"]


def test_admin_profile_overrides_env(db, monkeypatch):
    from app.models import LLMProfile
    from app.modules import persona_llm

    db.add(LLMProfile(
        name="fast", provider="tokenrhythm",
        base_url="https://tokenrhythm.studio/v1", model="egg-alpha",
        api_key_enc=persona_llm.encrypt_key("admin-key"),
        input_price_cny_per_m=1.0, output_price_cny_per_m=2.0,
    ))
    db.commit()
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings(
        llm_fast_api_key="env-key", llm_fast_model="glm-4-flash"))
    called = {}

    def fake_call(profile, messages, **kw):
        called["model"] = profile["model"]
        called["key"] = profile["api_key"]
        return "ok", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(llm_gateway, "_call", fake_call)
    result = llm_gateway.complete(db, "open_chat", _msgs())
    assert result.degraded is False
    assert called == {"model": "egg-alpha", "key": "admin-key"}
    assert result.profile == "fast"


def test_admin_profile_without_key_falls_back_env(db, monkeypatch):
    from app.models import LLMProfile

    db.add(LLMProfile(name="fast", provider="glm", base_url="https://example.invalid/v4",
                      model="admin-model", api_key_enc=""))
    db.commit()
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings(
        llm_fast_api_key="env-key", llm_fast_model="glm-4-flash"))

    def fake_call(profile, messages, **kw):
        return "ok", {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(llm_gateway, "_call", fake_call)
    result = llm_gateway.complete(db, "open_chat", _msgs())
    assert result.degraded is False
    assert result.model == "glm-4-flash"


def test_admin_disabled_profile_blocks_env_fallback(db, monkeypatch):
    from app.models import LLMProfile
    from app.modules import persona_llm

    db.add(LLMProfile(
        name="fast", provider="glm", base_url="https://example.invalid/v4",
        model="glm-4-flash", api_key_enc=persona_llm.encrypt_key("admin-key"),
        enabled=False,
    ))
    db.commit()
    monkeypatch.setattr(llm_gateway, "_settings", lambda: _settings(
        llm_fast_api_key="env-key"))
    result = llm_gateway.complete(db, "open_chat", _msgs())
    assert result.degraded is True
    assert result.error_class == "disabled"
