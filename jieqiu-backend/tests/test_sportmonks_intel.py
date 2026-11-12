"""Sportmonks 结构化情报：解析、落库、聚焦覆盖。"""
from __future__ import annotations

from datetime import datetime

from app.models import (SPMatch, SPSnapshot, SportmonksFixtureIntel,
                        SportmonksMatchData, SportmonksMarket,
                        SportmonksPrediction, Verdict, utcnow)
from app.modules import sportmonks_intel as si
from tests.conftest import CN, future_kickoff, today_cn


def _fixture() -> dict:
    return {
        "id": 9001,
        "starting_at": "2026-11-12 17:00:00",
        "league": {"name": "欧国联"},
        "season_id": 1,
        "season": {"name": "2026"},
        "round_id": 2,
        "round": {"name": "小组赛"},
        "participants": [
            {"id": 10, "name": "主队", "meta": {"location": "home"}},
            {"id": 20, "name": "客队", "meta": {"location": "away"}},
        ],
        "formations": [
            {"participant_id": 10, "location": "home", "formation": "4-4-2"},
            {"participant_id": 20, "location": "away", "formation": "4-3-3"},
        ],
        "lineups": [
            {"team_id": 10, "player_id": 1, "player_name": "主队门将",
             "type_id": 11, "jersey_number": 1, "position_id": 24,
             "formation_field": "1:1", "formation_position": 1},
            {"team_id": 20, "player_id": 2, "player_name": "客队前锋",
             "type_id": 11, "jersey_number": 9, "position_id": 27,
             "formation_field": "1:1", "formation_position": 1},
        ],
        "coaches": [
            {"name": "主教练甲", "meta": {"participant_id": 10}},
            {"name": "主教练乙", "meta": {"participant_id": 20}},
        ],
        "referees": [{"referee_id": 7, "type_id": 6}],
        "sidelined": [],
        "weatherreport": {"description": "多云"},
        "venue": {"name": "球场", "city_name": "城市"},
    }


def test_lineups_and_h2h_scores_keep_home_away_order():
    fixture = _fixture()
    by_side, by_team = si._participants(fixture)
    lineups = si._lineups(fixture, by_side, by_team)
    assert lineups["home"]["formation"] == "4-4-2"
    assert lineups["away"]["formation"] == "4-3-3"
    assert lineups["home"]["starters"][0]["name"] == "主队门将"

    h2h = {
        "id": 1,
        "starting_at": "2026-10-01 00:00:00",
        "participants": [
            {"id": 10, "name": "主队", "meta": {"location": "home"}},
            {"id": 20, "name": "客队", "meta": {"location": "away"}},
        ],
        "scores": [
            {"participant_id": 20, "type_id": 1525, "score": {"goals": 3}},
            {"participant_id": 10, "type_id": 1525, "score": {"goals": 1}},
        ],
    }
    result = si._fixture_result(h2h)
    assert result is not None
    assert result["score_home"] == 1
    assert result["score_away"] == 3


def test_lineups_prefer_localized_player_name():
    fixture = _fixture()
    fixture["lineups"][0]["player"] = {"id": 1, "name": "乌古尔詹·恰克尔"}
    by_side, by_team = si._participants(fixture)
    lineups = si._lineups(fixture, by_side, by_team)
    assert lineups["home"]["starters"][0]["name"] == "乌古尔詹·恰克尔"


def test_player_lookup_requests_chinese_locale(monkeypatch):
    captured = {}

    def fake_get(base, path, params):
        captured["path"] = path
        captured["params"] = params
        return {"data": {"id": 99, "name": "中文球员"}}

    monkeypatch.setattr(si, "_get", fake_get)
    si._PLAYER_CACHE.clear()
    assert si._player(99)["name"] == "中文球员"
    assert "locale=zh" in captured["params"]


def test_localize_staff_translates_coaches_and_referee(monkeypatch):
    from types import SimpleNamespace
    import app.modules.llm_gateway as llm

    def fake_complete(*args, **kwargs):
        return SimpleNamespace(
            degraded=False,
            text='{"translations":{"Mark van Bommel":"马克·范博梅尔",'
                 '"Sandro Schärer":"桑德罗·舍雷尔"}}',
        )

    monkeypatch.setattr(llm, "complete", fake_complete)
    payload = {
        "coaches": {"home": {"name": "Mark van Bommel"},
                    "away": {"name": "Mark van Bommel"}},
        "referees": {"main": {"name": "Sandro Schärer"}},
    }
    out = si._localize_staff(None, payload)
    assert out["coaches"]["home"]["name"] == "马克·范博梅尔"
    assert out["coaches"]["home"]["name_original"] == "Mark van Bommel"
    assert out["referees"]["main"]["name"] == "桑德罗·舍雷尔"


def test_sync_fixture_intel_persists_all_sections(db, monkeypatch):
    match = SPMatch(match_id="sm-intel-1", match_no="周四901", league="欧国联",
                    home_raw="主队", away_raw="客队", home="主队", away="客队",
                    kickoff=future_kickoff(today_cn()), single_flag=True)
    db.add(match)
    db.commit()

    detailed = _fixture()
    monkeypatch.setattr(si, "_fetch_fixture", lambda *args: detailed)
    monkeypatch.setattr(si, "_referees", lambda fixture: {
        "main": {"id": 7, "name": "主裁甲", "role": "主裁"},
        "crew_count": 4, "crew": [],
    })
    monkeypatch.setattr(si, "_sidelined", lambda fixture, by_side: [
        {"player_id": 2, "player_name": "客队前锋", "side": "away",
         "team_id": 20, "type_id": 551, "type_label": "伤停"},
    ])
    monkeypatch.setattr(si, "_standings", lambda *args: {
        "round_id": 2, "season_id": 1,
        "home": {"position": 2, "points": 6, "form": ["W", "D"]},
        "away": {"position": 1, "points": 9, "form": ["W", "W"]},
    })
    monkeypatch.setattr(si, "_h2h", lambda *args: [
        {"date": "2026-10-01", "home": "主队", "away": "客队",
         "score_home": 1, "score_away": 3},
    ])
    monkeypatch.setattr(si, "_predictions", lambda *args: ([{
        "type_id": 231, "type_code": "BTTS_PROBABILITY",
        "type_name": "双方进球", "probabilities": {"yes": 61.5, "no": 38.5},
    }], {"items": []}))
    monkeypatch.setattr(si, "_market_board", lambda *args: [{
        "key": "ou", "name": "大小球", "bookmaker": "Pinnacle", "line": "2.5",
        "selections": [{"label": "大 2.5", "price": 1.9, "probability": 52.6}],
    }])
    monkeypatch.setattr(si, "_facts", lambda *args: [{
        "type_id": 1, "type_code": "H2H", "type_name": "交锋",
        "category": "statistics", "scope": "all", "basis": "h2h",
        "text": "主队与客队有过交手。",
    }])

    result = si.sync_fixture_intel(db, "https://example.invalid", "token", match,
                                  {"id": 9001})
    db.commit()
    assert result["ok"] is True
    assert result["lineups"] == 2
    row = db.get(SportmonksFixtureIntel, "sm-intel-1")
    assert row is not None
    assert row.payload["formations"]["home"] == "4-4-2"
    assert row.payload["standings"]["home"]["position"] == 2
    assert row.payload["referees"]["main"]["name"] == "主裁甲"
    assert db.get(SportmonksPrediction, 1) is not None or db.query(
        SportmonksPrediction).filter_by(match_id="sm-intel-1").count() == 1
    assert db.query(SportmonksMarket).filter_by(match_id="sm-intel-1").count() == 1


def test_postmatch_intel_adds_score_xg_and_goals(db, monkeypatch):
    match = SPMatch(match_id="sm-intel-post", match_no="周四903", league="欧国联",
                    home_raw="主队", away_raw="客队", home="主队", away="客队",
                    kickoff="2026-11-10 20:00:00", single_flag=True)
    db.add(match)
    db.add(SportmonksFixtureIntel(
        match_id="sm-intel-post", fixture_id=9003, league="欧国联",
        home_name="主队", away_name="客队", kickoff_utc="2026-11-10 12:00:00",
        payload={"schema": "sportmonks-intel-v1"}, captured_at=utcnow(),
        data_cutoff="2026-11-10T12:00:00",
    ))
    db.commit()

    def fake_get(*args, **kwargs):
        return {"data": {
            "state": {"short_name": "FT"},
            "participants": [
                {"id": 10, "name": "主队", "meta": {"location": "home"}},
                {"id": 20, "name": "客队", "meta": {"location": "away"}},
            ],
            "scores": [
                {"participant_id": 10, "type_id": 1525, "score": {"goals": 2}},
                {"participant_id": 20, "type_id": 1525, "score": {"goals": 1}},
            ],
            "events": [
                {"type_id": 14, "participant_id": 10, "player_name": "甲",
                 "player": {"name": "甲（中文）"}, "minute": 12, "result": "1-0"},
            ],
            "xgfixture": [
                {"type_id": 5304, "location": "home", "data": {"value": 1.8}},
                {"type_id": 5304, "location": "away", "data": {"value": 1.1}},
            ],
        }}

    monkeypatch.setattr(si, "_get", fake_get)
    assert si.sync_postmatch_intel(db, "base", "token", match, 9003) is True
    db.commit()
    row = db.get(SportmonksFixtureIntel, "sm-intel-post")
    assert row is not None
    post = row.payload["postmatch"]
    assert post["score_home"] == 2 and post["score_away"] == 1
    assert post["xg_home"] == 1.8 and post["xg_away"] == 1.1
    assert post["goals"][0]["player"] == "甲（中文）"


def test_focus_uses_sportmonks_lineups_and_standings(client, db):
    kickoff = future_kickoff(today_cn())
    now = datetime.now(CN).strftime("%Y-%m-%d %H:%M:%S")
    db.add(SPMatch(match_id="sm-intel-2", match_no="周四902", league="欧国联",
                   home_raw="主队", away_raw="客队", home="主队", away="客队",
                   kickoff=kickoff, single_flag=True))
    db.add(SPSnapshot(match_id="sm-intel-2", pool="had", goal_line="",
                      sp_h=2.0, sp_d=3.5, sp_a=4.0, captured_at=now))
    db.add(Verdict(
        id="v-sm-intel-2", trade_date=today_cn(), match_id="sm-intel-2",
        match_no="周四902", league="欧国联", home="主队", away="客队",
        kickoff=kickoff, pool="had", goal_line="", sp_h=2.0, sp_d=3.5, sp_a=4.0,
        rake=0.08, p_home=0.45, p_draw=0.27, p_away=0.28,
        model_h=0.55, model_d=0.25, model_a=0.20,
        pick={"dir": "主胜", "prob": 0.55, "sp": 2.0},
        rake_threshold=0.13, status="promoted", tier="verified",
        gates={"price": {"result": "pass"}, "market": {"result": "pass"},
               "model": {"result": "pass"}},
        payload={"model": {"engine": "DC"}, "data_cutoff": now},
        payload_hash="b" * 64,
    ))
    db.add(SportmonksMatchData(
        match_id="sm-intel-2", fixture_id=9002,
        probs={"home": 0.5, "draw": 0.27, "away": 0.23},
        odds={"home": 0.48, "draw": 0.28, "away": 0.24},
        bookmaker="Pinnacle", source="sportmonks", captured_at=utcnow(),
        data_cutoff=now,
    ))
    db.add(SportmonksFixtureIntel(
        match_id="sm-intel-2", fixture_id=9002, league="欧国联",
        home_name="主队", away_name="客队", kickoff_utc="2026-11-12 17:00:00",
        payload={
            "lineups": {
                "home": {"team_name": "主队", "formation": "4-4-2",
                         "starters": [{"name": "甲"}]},
                "away": {"team_name": "客队", "formation": "4-3-3",
                         "starters": [{"name": "乙"}]},
            },
            "standings": {
                "home": {"position": 2, "points": 6, "form": ["W"]},
                "away": {"position": 1, "points": 9, "form": ["W"]},
            },
            "sidelined": [],
            "h2h": [{"date": "2026-10-01", "home": "主队", "away": "客队",
                     "score_home": 1, "score_away": 3}],
            "referees": {"main": {"name": "主裁甲"}, "crew_count": 4},
            "venue": {"name": "球场", "city": "城市"},
        },
        captured_at=utcnow(), expires_at=None, data_cutoff=now,
    ))
    db.commit()

    data = client.get("/matches/sm-intel-2/focus").json()
    assert data["coverage"]["score"] >= 75
    assert "lineups" not in data["coverage"]["missing"]
    assert "standings" not in data["coverage"]["missing"]
    assert data["intel"]["sportmonks"]["lineups"]["home"]["formation"] == "4-4-2"
    assert any(f["id"] == "lineups" for f in data["intel"]["facts"])
    assert "首发/伤停未接入" not in data["intel"]["unknowns"]
    assert "积分榜未同步" not in data["intel"]["unknowns"]
