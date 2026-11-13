"""API-Football 免费档同步与 focus 集成。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.features.intel import service as intel_service
from app.models import (ApiFootballFixture, MatchInjury, MatchLineup, SPMatch,
                        SPSnapshot, TeamAlias, TeamStanding, Verdict)
from app.modules import api_football
from app.modules.align import normalize
from tests.conftest import admin_login, future_kickoff, today_cn

CN = timezone(timedelta(hours=8))


def _seed_match(db):
    kickoff = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="af-match-1", match_no="周三950", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    now = datetime.now(CN)
    db.merge(SPSnapshot(match_id="af-match-1", pool="had", goal_line="",
                        sp_h=1.80, sp_d=3.50, sp_a=4.20,
                        captured_at=now.strftime("%Y-%m-%d %H:%M:%S")))
    db.merge(Verdict(
        id="v-af-1", trade_date=today_cn(), match_id="af-match-1", match_no="周三950",
        league="英超", home="曼城", away="曼联", kickoff=kickoff,
        pool="had", goal_line="", sp_h=1.80, sp_d=3.50, sp_a=4.20,
        rake=0.121, p_home=0.56, p_draw=0.23, p_away=0.21,
        model_h=0.61, model_d=0.22, model_a=0.17,
        pick={"dir": "主胜", "prob": 0.61, "sp": 1.80}, rake_threshold=0.13,
        status="screening",
        gates={"price": {"result": "pass"}, "market": {"result": "pending_data"},
               "model": {"result": "pass"}},
        payload={"model": {"engine": "DC v1.1", "shrunk": [0.61, 0.22, 0.17]},
                 "data_cutoff": now.strftime("%Y-%m-%d %H:%M:%S"),
                 "evidence": []},
        payload_hash="b" * 64,
    ))
    for alias, canonical in (("Manchester City", "曼城"), ("Manchester United", "曼联")):
        db.merge(TeamAlias(alias=normalize(alias), canonical=canonical))
    db.commit()
    dt = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
    return kickoff, dt.astimezone(timezone.utc).isoformat()


def _fixture_item(kickoff_utc: str):
    return {
        "fixture": {"id": 999001, "date": kickoff_utc,
                    "status": {"short": "NS", "long": "Not Started"},
                    "venue": {"name": "Etihad"}},
        "league": {"id": 39, "name": "Premier League", "season": 2026},
        "teams": {
            "home": {"id": 10, "name": "Manchester City"},
            "away": {"id": 20, "name": "Manchester United"},
        },
    }


def test_sync_fixtures_auto_links_via_alias(client, db, monkeypatch):
    _, kickoff_utc = _seed_match(db)
    monkeypatch.setattr(api_football, "_request",
                        lambda db, endpoint, params=None: [_fixture_item(kickoff_utc)])
    out = api_football.sync_fixtures(db, today_cn())
    assert out["fixtures"] == 1 and out["linked"] == 1
    row = db.get(ApiFootballFixture, 999001)
    assert row is not None and row.match_id == "af-match-1"
    assert row.link_method == "auto" and row.link_confidence >= 0.95


def test_sync_lineups_injuries_standings_and_focus(client, db, monkeypatch):
    _, kickoff_utc = _seed_match(db)

    def fake(db, endpoint, params=None):
        if endpoint == "fixtures/lineups":
            return [
                {"team": {"id": 10, "name": "Manchester City"}, "formation": "4-3-3",
                 "coach": {"name": "Pep"}, "startXI": [
                     {"player": {"id": 1, "name": "Ederson", "number": 31, "pos": "G"}},
                     {"player": {"id": 2, "name": "Walker", "number": 2, "pos": "D"}},
                 ], "substitutes": [{"player": {"id": 3, "name": "Sub"}}]},
                {"team": {"id": 20, "name": "Manchester United"}, "formation": "4-2-3-1",
                 "coach": {"name": "Ten Hag"}, "startXI": [
                     {"player": {"id": 4, "name": "Onana", "number": 24, "pos": "G"}},
                 ], "substitutes": []},
            ]
        if endpoint == "injuries":
            return [{"team": {"id": 10, "name": "Manchester City"},
                     "player": {"id": 7, "name": "Stones",
                                "type": "Missing Fixture", "reason": "Injury"},
                     "fixture": {"status": "NS"}}]
        if endpoint == "standings":
            return [{"league": {"standings": [[
                {"rank": 1, "team": {"id": 10, "name": "Manchester City"},
                 "points": 30, "all": {"played": 12, "win": 9, "draw": 3, "lose": 0,
                                       "goals": {"for": 28, "against": 8}}, "form": "WWWDW"},
                {"rank": 2, "team": {"id": 20, "name": "Manchester United"},
                 "points": 25, "all": {"played": 12, "win": 8, "draw": 1, "lose": 3,
                                       "goals": {"for": 20, "against": 15}}, "form": "WLWWW"},
            ]]}}]
        if endpoint == "fixtures":
            return [_fixture_item(kickoff_utc)]
        raise AssertionError(endpoint)

    monkeypatch.setattr(api_football, "_request", fake)
    api_football.sync_fixtures(db, today_cn())
    assert api_football.sync_lineups(db, hours=24)["synced"] == 1
    assert api_football.sync_injuries(db, hours=24)["synced"] == 1
    assert api_football.sync_standings(db)["synced"] == 1
    assert len(db.query(MatchLineup).all()) == 2
    injury = db.query(MatchInjury).one()
    assert injury.type == "Missing Fixture" and injury.reason == "Injury"
    assert len(db.query(TeamStanding).all()) == 2

    focus = intel_service.build_focus(db, "af-match-1", persona="zhuanjia")
    assert focus is not None
    kinds = {f["kind"] for f in focus["intel"]["facts"]}
    assert {"lineup", "injury", "standing"} <= kinds
    source = {s["key"]: s for s in focus["coverage"]["sources"]}
    assert source["lineups"]["status"] == "ok"
    assert source["standings"]["status"] == "ok"
    assert set(focus["coverage"]["missing"]) == {"market", "sportmonks_intel"}


def test_lineup_snapshot_replaces_stale_side(client, db, monkeypatch):
    _, kickoff_utc = _seed_match(db)
    state = {"home_only": False}

    def fake(db, endpoint, params=None):
        if endpoint == "fixtures":
            return [_fixture_item(kickoff_utc)]
        if endpoint == "fixtures/lineups":
            rows = [{"team": {"id": 10, "name": "Manchester City"}, "formation": "4-3-3",
                     "startXI": [{"player": {"id": 1, "name": "Ederson"}}]}]
            if not state["home_only"]:
                rows.append({"team": {"id": 20, "name": "Manchester United"},
                             "formation": "4-2-3-1",
                             "startXI": [{"player": {"id": 4, "name": "Onana"}}]})
            return rows
        raise AssertionError(endpoint)

    monkeypatch.setattr(api_football, "_request", fake)
    api_football.sync_fixtures(db, today_cn())
    api_football.sync_lineups(db, hours=24)
    assert db.query(MatchLineup).count() == 2
    fixture = db.query(ApiFootballFixture).one()
    fixture.lineups_synced_at = None
    state["home_only"] = True
    db.commit()
    api_football.sync_lineups(db, hours=24)
    assert db.query(MatchLineup).count() == 1
    assert db.query(MatchLineup).one().side == "home"


def test_quota_enforced(db, monkeypatch):
    monkeypatch.setattr(api_football, "_settings", lambda: SimpleNamespace(
        api_football_daily_limit=1, api_football_key="x",
        api_football_base_url="https://example.invalid", api_football_timeout_s=1,
    ))
    api_football.consume_quota(db, "fixtures")
    with pytest.raises(api_football.ApiFootballBudgetExceeded):
        api_football.consume_quota(db, "fixtures")


def test_admin_ops_reports_aux_football_status(client, db):
    admin_login(client)
    data = client.get("/admin/api/ops").json()
    assert "football" in data
    assert "football_fixtures" not in data


def test_provider_base_url_and_headers():
    from types import SimpleNamespace
    from app.modules import api_football

    st = SimpleNamespace(api_football_provider="apisports",
                         api_football_base_url="https://v3.football.api-sports.io/",
                         api_football_key="k1")
    base, headers = api_football._base_url_and_headers(st)
    assert base == "https://v3.football.api-sports.io"
    assert headers["x-apisports-key"] == "k1"

    st = SimpleNamespace(api_football_provider="rapidapi",
                         api_football_base_url="https://v3.football.api-sports.io",
                         api_football_rapidapi_host="api-football-v1.p.rapidapi.com",
                         api_football_key="k2")
    base, headers = api_football._base_url_and_headers(st)
    assert base == "https://api-football-v1.p.rapidapi.com/v3"
    assert headers["x-rapidapi-key"] == "k2"
    assert headers["x-rapidapi-host"] == "api-football-v1.p.rapidapi.com"


def test_sync_injuries_dedupes_duplicate_rows(client, db, monkeypatch):
    """API 会重复返回同一球员同类型伤停；唯一键只允许一条。"""
    _, kickoff_utc = _seed_match(db)

    def fake(db, endpoint, params=None):
        if endpoint == "fixtures":
            return [_fixture_item(kickoff_utc)]
        if endpoint == "injuries":
            item = {"team": {"id": 10, "name": "Manchester City"},
                    "player": {"id": 7, "name": "Stones", "type": "Missing Fixture",
                               "reason": "Injury"},
                    "fixture": {"status": "NS"}}
            return [item, item]
        raise AssertionError(endpoint)

    monkeypatch.setattr(api_football, "_request", fake)
    api_football.sync_fixtures(db, today_cn())
    out = api_football.sync_injuries(db, hours=24)
    assert out["synced"] == 1
    assert db.query(MatchInjury).count() == 1


def test_sync_all_next_day_fetches_two_dates(db, monkeypatch):
    dates = []

    def fake(db, endpoint, params=None):
        if endpoint == "fixtures":
            dates.append(params["date"])
            return []
        return []

    monkeypatch.setattr(api_football, "_request", fake)
    out = api_football.sync_all(db, date="2026-11-05", include_next_day=True)
    assert dates == ["2026-11-05", "2026-11-06"]
    assert out["next_date"] == "2026-11-06"
