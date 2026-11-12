"""人设语气翻译：加密、默认模型池、failover、缓存、后台页面。"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models import PersonaCopyCache, PersonaLLMModel, PersonaProfile
from app.modules import persona_registry
from app.modules import persona_llm
from tests.conftest import admin_login


def test_legacy_meng_default_is_migrated(db):
    """旧库里的“萌妹萝莉/主人”默认值必须升级，避免继续面向博彩用户展示。"""
    db.add(PersonaProfile(
        id="meng", name="萌妹萝莉", address="主人", tone="主人 · 小女仆 · 勤快",
        style_prompt="旧提示词", max_chars=240, emoji_policy="limited",
        allowed_emoji="♡～", version=1, enabled=True,
    ))
    db.commit()

    persona_registry.ensure_seeded(db)

    row = db.get(PersonaProfile, "meng")
    assert row.name == "元气搭子"
    assert row.address == "你"
    assert row.version == 2


def _settings(**over):
    base = dict(
        persona_llm_base_url="https://tokenrhythm.studio/v1",
        persona_llm_api_key="test-key",
        persona_llm_enc_key="test-secret",
        persona_llm_timeout_s=5,
        persona_llm_max_tokens=800,
        persona_llm_temperature=0.4,
        persona_llm_cooldown_s=60,
        jwt_secret="jwt-test",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _use(monkeypatch, **over):
    monkeypatch.setattr(persona_llm, "get_settings", lambda: _settings(**over))


def _model(db, model: str, priority: int, key: str = "k") -> PersonaLLMModel:
    row = PersonaLLMModel(name=model, base_url="https://example.invalid/v1",
                          model=model, api_key_enc=persona_llm.encrypt_key(key),
                          priority=priority, enabled=True)
    db.add(row)
    db.commit()
    return row


def test_key_encryption_roundtrip(monkeypatch):
    _use(monkeypatch)
    enc = persona_llm.encrypt_key("sk-test-123")
    assert "sk-test" not in enc
    assert persona_llm.decrypt_key(enc) == "sk-test-123"
    assert persona_llm.mask_key(enc) == "已配置"


def test_default_model_pool(monkeypatch, db):
    _use(monkeypatch)
    n = persona_llm.ensure_default_models(db)
    assert n == 2
    rows = persona_llm.list_models(db)
    assert [r.model for r in rows] == ["egg-alpha", "neohorse-1-9b"]
    assert all(persona_llm.decrypt_key(r.api_key_enc) == "test-key" for r in rows)


def test_default_models_backfill_key(monkeypatch, db):
    _use(monkeypatch, persona_llm_api_key="")
    persona_llm.ensure_default_models(db)
    rows = persona_llm.list_models(db)
    assert all(r.api_key_enc == "" for r in rows)
    _use(monkeypatch, persona_llm_api_key="later-key")
    persona_llm.ensure_default_models(db)
    rows = persona_llm.list_models(db)
    assert all(persona_llm.decrypt_key(r.api_key_enc) == "later-key" for r in rows)


def test_update_key_and_error_scrub(monkeypatch, db):
    _use(monkeypatch)
    row = _model(db, "egg-alpha", 1)
    persona_llm.update_key(db, row.id, "new-secret")
    assert persona_llm.decrypt_key(row.api_key_enc) == "new-secret"
    assert "sk-secret" not in persona_llm._scrub_error("HTTP 401 key=sk-secret12345678")


def test_failover_and_cache(monkeypatch, db):
    _use(monkeypatch)
    first = _model(db, "egg-alpha", 1)
    second = _model(db, "neohorse-1-9b", 2)
    calls = []

    def fake(row, text, persona, **kw):
        calls.append(row.model)
        if row.model == "egg-alpha":
            raise persona_llm.PersonaLLMError("HTTP 409: upstream failed")
        return "兄弟，今天先看成本。", {"prompt_tokens": 10, "completion_tokens": 10}, 120

    monkeypatch.setattr(persona_llm, "_call_model", fake)
    r = persona_llm.translate(db, "今天先看成本。", "laopao",
                              source_key="verdict:v1", source_hash="h1")
    assert r.model == "neohorse-1-9b"
    assert "成本" in r.text
    assert calls == ["egg-alpha", "neohorse-1-9b"]
    assert db.query(PersonaCopyCache).count() == 1
    assert first.fail_count == 1
    assert second.fail_count == 0

    calls.clear()
    r2 = persona_llm.translate(db, "今天先看成本。", "laopao",
                               source_key="verdict:v1", source_hash="h1")
    assert r2.cached is True
    assert calls == []


def test_cache_invalidated_by_profile_version(monkeypatch, db):
    _use(monkeypatch)
    _model(db, "egg-alpha", 1)
    calls = {"n": 0}

    def fake(row, text, persona, **kw):
        calls["n"] += 1
        return f"第{calls['n']}版", {}, 10

    monkeypatch.setattr(persona_llm, "_call_model", fake)
    r1 = persona_llm.translate(db, "今天看成本。", "laopao",
                               source_key="verdict:v2", source_hash="h2")
    persona_registry.update_profile(db, "laopao", address="老铁")
    r2 = persona_llm.translate(db, "今天看成本。", "laopao",
                               source_key="verdict:v2", source_hash="h2")
    assert r1.cached is False and r2.cached is False
    assert calls["n"] == 2


def test_partial_slot_seed_and_emoji_prompt(monkeypatch, db):
    _use(monkeypatch)
    persona_registry.ensure_seeded(db)
    db.query(persona_registry.PersonaCopySlot).filter_by(
        persona_id="meng", slot_key="today_pick").delete()
    db.commit()
    persona_registry.ensure_seeded(db)
    assert db.query(persona_registry.PersonaCopySlot).filter_by(
        persona_id="meng", slot_key="today_pick").count() == 1
    persona_registry.update_profile(db, "meng", emoji_policy="limited",
                                    allowed_emoji="♡")
    prompt = persona_llm._system_prompt("meng", db)
    assert "limited" in prompt and "♡" in prompt


def test_all_models_fail(monkeypatch, db):
    _use(monkeypatch)
    _model(db, "egg-alpha", 1)
    _model(db, "neohorse-1-9b", 2)
    monkeypatch.setattr(persona_llm, "_call_model",
                        lambda *a, **k: (_ for _ in ()).throw(
                            persona_llm.PersonaLLMError("down")))
    with pytest.raises(persona_llm.PersonaLLMError):
        persona_llm.translate(db, "test", "zhuanjia")


def test_public_personas_config(client, db):
    r = client.get("/personas")
    assert r.status_code == 200
    data = r.json()
    assert {p["id"] for p in data["profiles"]} == {"zhuanjia", "laopao", "meng"}
    assert len(data["slots"]) >= 21  # 9 个叙述 slot + 12 个前端 slot
    slots = {(s["persona_id"], s["slot_key"]): s["template"] for s in data["slots"]}
    # 3 人设不变，但同一 slot 的文案必须真正不同。
    assert slots[("zhuanjia", "brandSub")] != slots[("laopao", "brandSub")]
    assert slots[("laopao", "emptyTitle")] != slots[("meng", "emptyTitle")]
    assert "style_prompt" not in data["profiles"][0]


def test_admin_update_profile_and_slot(client, db, monkeypatch):
    _use(monkeypatch)
    admin_login(client)
    assert client.put("/admin/api/personas/laopao", json={
        "address": "老铁", "tone": "老铁 · 直接", "style_prompt": "短句，直接。",
        "max_chars": 180, "emoji_policy": "none", "allowed_emoji": "",
    }).status_code == 200
    assert client.put("/admin/api/personas/laopao/slots/today_pick", json={
        "template": "老铁，今天看 {home} vs {away}。", "enabled": True,
    }).status_code == 200
    data = client.get("/admin/api/personas").json()
    assert "brandSub" in data["slot_keys"]
    assert "narration_promoted" in data["slot_keys"]
    profile = next(p for p in data["profiles"] if p["id"] == "laopao")
    assert profile["address"] == "老铁"
    assert profile["max_chars"] == 180
    prompt = persona_llm._system_prompt("laopao", db)
    assert "老铁" in prompt and "短句" in prompt


def test_admin_persona_test_endpoint(client, db, monkeypatch):
    _use(monkeypatch)
    admin_login(client)
    monkeypatch.setattr(persona_llm, "_call_model",
                        lambda row, text, persona, **kw: ("改写后", {"prompt_tokens": 1,
                                                              "completion_tokens": 1}, 30))
    r = client.post("/admin/api/persona/test",
                    json={"persona": "laopao", "text": "今天先看成本。"})
    assert r.status_code == 200
    assert r.json()["text"] == "改写后"


def test_admin_add_model_encrypts_key(client, db, monkeypatch):
    _use(monkeypatch)
    admin_login(client)
    r = client.post("/admin/api/models", json={
        "name": "Test Model",
        "base_url": "https://example.invalid/v1",
        "model": "test-model",
        "api_key": "sk-secret-123",
        "priority": 30,
        "max_tokens": 500,
        "temperature": 0.5,
    })
    assert r.status_code == 200, r.text
    row = db.query(PersonaLLMModel).filter(PersonaLLMModel.model == "test-model").one()
    assert "sk-secret" not in row.api_key_enc
    assert persona_llm.decrypt_key(row.api_key_enc) == "sk-secret-123"


def test_warm_verdicts(monkeypatch, db):
    _use(monkeypatch)
    from app.models import SPMatch, Verdict
    from tests.conftest import future_kickoff, today_cn
    mid = "persona-warm-1"
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id=mid, match_no="周三860", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kick, single_flag=True))
    db.merge(Verdict(
        id="v-persona-warm", trade_date=today_cn(), match_id=mid, match_no="周三860",
        league="英超", home="曼城", away="曼联", kickoff=kick,
        pool="had", goal_line="", sp_h=1.8, sp_d=3.5, sp_a=4.2,
        rake=0.12, p_home=0.52, p_draw=0.27, p_away=0.21,
        model_h=0.56, model_d=0.24, model_a=0.20,
        pick={"dir": "主胜", "prob": 0.56}, rake_threshold=0.13, status="promoted",
        gates={"price": {"result": "pass"}, "market": {"result": "pass"},
               "model": {"result": "pass"}},
        payload={"data_cutoff": datetime.now(timezone.utc).isoformat()},
        payload_hash="w" * 64,
        sealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    _model(db, "egg-alpha", 1)
    monkeypatch.setattr(persona_llm, "_call_model",
                        lambda row, text, persona, **kw: (f"{persona}文案", {}, 20))
    out = persona_llm.warm_verdicts(db, today_cn())
    assert out["ok"] == 3
    assert db.query(PersonaCopyCache).count() == 3
