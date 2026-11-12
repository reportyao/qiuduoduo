"""Sportmonks 赛果回填测试。"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import MatchResult, SPMatch, SportmonksMatchData
from app.modules.sportmonks_results import parse_score, sync_results
from app.modules.timeutil import CN


def _fixture(state="FT", home=2, away=1, result_info=None):
    return {
        "id": 700001,
        "state": {"short_name": state},
        "result_info": result_info,
        "scores": [
            {"type_id": 1525, "description": "CURRENT",
             "score": {"participant": "home", "goals": home}},
            {"type_id": 1525, "description": "CURRENT",
             "score": {"participant": "away", "goals": away}},
        ],
    }


def test_parse_score_only_finished():
    assert parse_score(_fixture()) == (2, 1)
    # AET/PEN 的 CURRENT 可能含加时点球，不能直接当 90 分钟。
    assert parse_score(_fixture(state="AET", home=3, away=2)) is None
    # 有明确 FT 行时，AET 场次仍可按 FT90 结算。
    fixture = _fixture(state="AET", home=3, away=2)
    fixture["scores"] = [
        {"type_id": 1525, "description": "FT",
         "score": {"participant": "home", "goals": 2}},
        {"type_id": 1525, "description": "FT",
         "score": {"participant": "away", "goals": 1}},
        {"type_id": 1525, "description": "CURRENT",
         "score": {"participant": "home", "goals": 3}},
        {"type_id": 1525, "description": "CURRENT",
         "score": {"participant": "away", "goals": 2}},
    ]
    assert parse_score(fixture) == (2, 1)
    assert parse_score(_fixture(state="NS")) is None
    assert parse_score(_fixture(state="1H")) is None
    assert parse_score({"state": {"short_name": "FT"}, "scores": [],
                        "result_info": "2-1"}) == (2, 1)


def test_sync_results_inserts_and_skips(db, monkeypatch):
    kickoff = (datetime.now(CN) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    mid = "sm-result-1"
    db.merge(SPMatch(match_id=mid, match_no="周三993", league="日联赛杯",
                     home_raw="横滨水手", away_raw="鹿岛鹿角",
                     home="横滨水手", away="鹿岛鹿角", kickoff=kickoff,
                     single_flag=True))
    db.merge(SportmonksMatchData(
        match_id=mid, fixture_id=700001, league="日联赛杯",
        home_name="横滨水手", away_name="鹿岛鹿角",
        kickoff_utc=kickoff, probs={"home": 0.4, "draw": 0.3, "away": 0.3},
        odds={"home": 0.42, "draw": 0.29, "away": 0.29},
        bookmaker="Pinnacle", data_cutoff="2026-11-11T12:00:00"))
    db.commit()

    from app.modules import sportmonks_results

    class _Settings:
        sportmonks_token = "test-token"
        sportmonks_base_url = "https://example.invalid/v3/football"

    monkeypatch.setattr(sportmonks_results, "get_settings", lambda: _Settings())
    monkeypatch.setattr(sportmonks_results, "_get",
                        lambda *a, **k: {"data": _fixture()})
    result = sync_results(db, days=2)
    assert result["ok"] is True
    assert result["inserted"] == 1
    row = db.scalar(select(MatchResult).where(
        MatchResult.home == "横滨水手", MatchResult.away == "鹿岛鹿角"))
    assert row is not None
    assert (row.goals_home, row.goals_away) == (2, 1)
    assert row.match_date == kickoff[:10]

    again = sync_results(db, days=2)
    assert again["inserted"] == 0
    assert again["skipped"] >= 1


def test_backfill_historical_verdict(db, monkeypatch):
    from datetime import timezone

    from app.models import Verdict
    from app.modules import sportmonks_results

    kickoff = (datetime.now(CN) - timedelta(days=1)).replace(
        hour=20, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    utc = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=CN).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.merge(Verdict(
        id="v-backfill-1", trade_date=kickoff[:10], match_id="backfill-1",
        match_no="周三994", league="日联赛杯", home="横滨水手", away="鹿岛鹿角",
        kickoff=kickoff, pool="had", goal_line="", sp_h=2.0, sp_d=3.4, sp_a=3.8,
        rake=0.09, p_home=0.45, p_draw=0.29, p_away=0.26,
        model_h=0.50, model_d=0.28, model_a=0.22,
        pick={"dir": "主胜", "prob": 0.50, "sp": 2.0}, rake_threshold=0.13,
        status="screening", gates={}, payload={}, payload_hash="a" * 64,
    ))
    db.commit()

    fixture = {
        "id": 700002, "starting_at": utc,
        "state": {"short_name": "FT"},
        "participants": [
            {"name": "横滨水手", "meta": {"location": "home"}},
            {"name": "鹿岛鹿角", "meta": {"location": "away"}},
        ],
        "scores": [
            {"type_id": 1525, "description": "CURRENT",
             "score": {"participant": "home", "goals": 2}},
            {"type_id": 1525, "description": "CURRENT",
             "score": {"participant": "away", "goals": 0}},
        ],
    }

    class _Settings:
        sportmonks_token = "test-token"
        sportmonks_base_url = "https://example.invalid/v3/football"

    monkeypatch.setattr(sportmonks_results, "get_settings", lambda: _Settings())
    monkeypatch.setattr(sportmonks_results, "_fetch_day", lambda *a, **k: [fixture])
    result = sportmonks_results.backfill_verdict_results(db, days=14)
    assert result["inserted"] == 1
    assert result["settled"] == 1
    db.expire_all()
    row = db.get(Verdict, "v-backfill-1")
    assert row.settled == "win"
    assert row.result_score == "2-0"
