"""Sportmonks 预测作为 DC 缺阵时的后备模型，必须可审计、可回退。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import (LeagueModelConfig, SPMatch, SPSnapshot,
                        SportmonksMatchData, utcnow)
from app.modules.sportmonks import handicap_probs, model_probs
from app.modules.verdict import build_verdicts
from tests.conftest import CN, future_kickoff, today_cn


def test_model_probs_validates_and_expires():
    sm = SportmonksMatchData(
        match_id="sm-model-1", fixture_id=1,
        probs={"home": 0.55, "draw": 0.25, "away": 0.20},
        captured_at=utcnow(),
    )
    assert model_probs(sm) == (0.55, 0.25, 0.20)

    sm.captured_at = utcnow() - timedelta(hours=7)
    assert model_probs(sm) is None

    sm.captured_at = utcnow()
    sm.probs = {"home": 0.9, "draw": 0.2, "away": 0.2}
    assert model_probs(sm) is None


def test_handicap_probs_use_correct_score_distribution():
    sm = SportmonksMatchData(
        match_id="sm-model-3", fixture_id=3,
        probs={
            "home": 0.50, "draw": 0.20, "away": 0.30,
            "scores": {"1-0": 50.0, "0-1": 30.0, "0-0": 20.0},
        },
        captured_at=utcnow(),
    )
    assert handicap_probs(sm, "0") == (0.5, 0.2, 0.3)
    assert handicap_probs(sm, "+1") == (0.7, 0.3, 0.0)
    assert handicap_probs(sm, "-1") == (0.0, 0.5, 0.5)
    assert handicap_probs(sm, "not-a-line") is None

    sm.probs = {"home": 0.50, "draw": 0.20, "away": 0.30}
    assert handicap_probs(sm, "+1") is None


def test_verdict_uses_sportmonks_prediction_when_dc_has_no_team(db):
    kick = future_kickoff(today_cn())
    db.add(SPMatch(match_id="sm-model-2", match_no="周四991", league="欧国联",
                   home_raw="土耳其", away_raw="比利时",
                   home="土耳其", away="比利时", kickoff=kick, single_flag=True))
    db.add(SPSnapshot(match_id="sm-model-2", pool="had", goal_line="",
                      sp_h=2.00, sp_d=3.50, sp_a=4.00,
                      captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.add(SportmonksMatchData(
        match_id="sm-model-2", fixture_id=991,
        probs={"home": 0.5452, "draw": 0.2156, "away": 0.2392},
        odds={"home": 0.49, "draw": 0.28, "away": 0.23},
        bookmaker="Pinnacle", source="sportmonks",
        captured_at=utcnow(), data_cutoff=utcnow().isoformat(),
    ))
    db.add(LeagueModelConfig(league="欧国联", dc_status="disabled",
                             sm_status="enabled", sm_weight=1.0))
    db.commit()

    now_cn = datetime.now(CN).strftime("%Y-%m-%d %H:%M:%S")
    verdicts = build_verdicts(db, today_cn(), now_cn)
    verdict = next(v for v in verdicts if v.match_id == "sm-model-2")

    assert verdict.gates["model"]["result"] == "pass"
    assert verdict.model_source == "sportmonks"
    assert verdict.model_status == "enabled"
    assert verdict.status == "promoted"
    assert verdict.tier == "verified"
    assert verdict.pick["dir"] == "主胜"
    assert any("Sportmonks 1X2" in ev.get("t", "") for ev in verdict.payload["evidence"])
