"""单场 AI 解读：缓存、覆盖门槛、输出校验。"""
from __future__ import annotations

from app.features.analysis import service as analysis
from app.models import AIAnalysis
from app.modules.llm_gateway import LLMResult
from tests.conftest import today_cn


def _focus(deep_eligible=True):
    return {
        "match": {"match_id": "m-ai-1", "match_no": "周四001",
                  "league": "英超", "home": "曼城", "away": "布莱顿",
                  "kickoff": f"{today_cn()} 20:00:00",
                  "sale_close": f"{today_cn()} 20:00:00", "single": True},
        "trade_date": today_cn(),
        "data_cutoff": f"{today_cn()}T18:00:00+08:00",
        "coverage": {"score": 85, "level": "full", "deep_eligible": deep_eligible,
                     "missing": [] if deep_eligible else ["lineups"]},
        "verdict": {"status": "promoted", "pick": {"dir": "主胜", "prob": 0.56},
                    "probs": {"home": 0.56, "draw": 0.25, "away": 0.19},
                    "gates": {"price": "pass", "market": "pass", "model": "pass"},
                    "rake": 0.12, "rake_threshold": 0.13},
        "intel": {"facts": [
            {"label": "竞彩官方 SP", "value": "1.80 / 3.50 / 4.20",
             "detail": "胜平负", "status": "confirmed",
             "captured_at": f"{today_cn()} 18:00:00"},
        ], "unknowns": ["首发未公布"]},
    }


def test_generate_is_cached_by_fact_hash(db, monkeypatch):
    monkeypatch.setattr(analysis.intel_service, "build_focus",
                        lambda *a, **k: _focus())
    calls = {"n": 0}

    def fake_complete(*args, **kwargs):
        calls["n"] += 1
        return LLMResult(
            text="{}", data={
                "summary": "主胜方向有价格与模型支撑，但首发未定。",
                "key_factors": ["主胜概率 56%", "抽水低于阈值"],
                "risks": ["首发未公布"], "invalidators": ["临场主胜 SP 明显抬升"],
                "data_gaps": ["首发未公布"], "confidence_note": "数据截止 18:00",
            }, provider="tokenrhythm", model="deepseek-v4.1-flash-1017",
            profile="deep")

    monkeypatch.setattr(analysis.llm_gateway, "complete", fake_complete)
    first = analysis.generate(db, "m-ai-1")
    second = analysis.generate(db, "m-ai-1")
    assert first["status"] == "ready"
    assert first["summary"].startswith("主胜方向")
    assert first["cached"] is False
    assert second["cached"] is True
    assert calls["n"] == 1
    assert db.query(AIAnalysis).count() == 1


def test_generate_requires_deep_eligible(db, monkeypatch):
    monkeypatch.setattr(analysis.intel_service, "build_focus",
                        lambda *a, **k: _focus(deep_eligible=False))
    result = analysis.generate(db, "m-ai-1")
    assert result["status"] == "unavailable"
    assert result["reason"] == "coverage"
    assert result["missing"] == ["lineups"]
    assert db.query(AIAnalysis).count() == 0


def test_generate_degrades_without_key(db, monkeypatch):
    monkeypatch.setattr(analysis.intel_service, "build_focus",
                        lambda *a, **k: _focus())
    monkeypatch.setattr(analysis.llm_gateway, "complete",
                        lambda *a, **k: LLMResult(
                            degraded=True, error_class="not_configured"))
    result = analysis.generate(db, "m-ai-1")
    assert result["status"] == "unavailable"
    assert result["reason"] == "not_configured"
    assert db.query(AIAnalysis).count() == 0


def test_cached_for_focus_reads_saved_analysis(db, monkeypatch):
    monkeypatch.setattr(analysis.intel_service, "build_focus",
                        lambda *a, **k: _focus())
    monkeypatch.setattr(analysis.llm_gateway, "complete",
                        lambda *a, **k: LLMResult(
                            text="{}", data={
                                "summary": "解读", "key_factors": ["a", "b"],
                                "risks": ["r"], "invalidators": ["i"],
                                "data_gaps": [], "confidence_note": "n",
                            }, provider="p", model="m", profile="deep"))
    analysis.generate(db, "m-ai-1")
    got = analysis.get_cached(db, "m-ai-1")
    assert got["status"] == "ready"
    assert got["cached"] is True


def test_analysis_endpoint_returns_ready_shape(client, monkeypatch):
    from app.features.analysis import service as analysis_service

    monkeypatch.setattr(analysis_service, "generate", lambda *a, **k: {
        "status": "ready", "summary": "解读", "key_factors": ["a"],
        "risks": ["r"], "invalidators": ["i"], "data_gaps": [],
        "confidence_note": "n", "model": "m", "generated_at": None,
        "data_cutoff": None, "cached": False,
    })
    response = client.post("/matches/m-ai/analysis")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["summary"] == "解读"
