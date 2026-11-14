"""比赛看板：即时/赛果隔离、预测快照锁定与 25 维结算。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.features.board import service
from app.models import (MatchResult, MatchResultDetail, SPMatch,
                        SPPoolSnapshot, SportmonksLiveState,
                        SportmonksMarket, SportmonksMatchData,
                        SportmonksPrediction,
                        SportmonksPredictionSettlement,
                        SportmonksPredictionSnapshot, User, Verdict,
                        WatchTarget, utcnow)
from tests.conftest import CN, future_kickoff, today_cn

CN_TZ = CN
UTC = timezone.utc

_PREDICTIONS = [
    (231, "BTTS_PROBABILITY", "双方进球", {"yes": 61.5, "no": 38.5}),
    (232, "HTFT_PROBABILITY", "半场/全场", {
        "home_home": 30.0, "home_draw": 3.0, "home_away": 2.0,
        "draw_home": 10.0, "draw_draw": 8.0, "draw_away": 6.0,
        "away_home": 2.0, "away_draw": 4.0, "away_away": 35.0}),
    (233, "FIRST_HALF_WINNER_PROBABILITY", "半场胜平负",
     {"home": 40.0, "draw": 30.0, "away": 30.0}),
    (234, "OVER_UNDER_1_5_PROBABILITY", "大小球1.5", {"yes": 82.0, "no": 18.0}),
    (235, "OVER_UNDER_2_5_PROBABILITY", "大小球2.5", {"yes": 62.0, "no": 38.0}),
    (236, "OVER_UNDER_3_5_PROBABILITY", "大小球3.5", {"yes": 40.0, "no": 60.0}),
    (237, "FULLTIME_RESULT_PROBABILITY", "全场胜平负",
     {"home": 37.0, "draw": 23.0, "away": 40.0}),
    (238, "TEAM_TO_SCORE_FIRST_PROBABILITY", "先得分球队",
     {"home": 40.0, "away": 55.0, "draw": 5.0}),
    (239, "DOUBLE_CHANCE_PROBABILITY", "双重机会",
     {"draw_home": 60.0, "draw_away": 63.0, "home_away": 77.0}),
    (240, "CORRECT_SCORE_PROBABILITY", "正确比分",
     {"scores": {"2-1": 8.0, "1-1": 9.0, "0-1": 7.0, "Other_1": 20.0}}),
    (326, "HOME_OVER_UNDER_3_5_PROBABILITY", "主队大小球3.5",
     {"yes": 7.0, "no": 93.0}),
    (327, "AWAY_OVER_UNDER_3_5_PROBABILITY", "客队大小球3.5",
     {"yes": 9.0, "no": 91.0}),
    (328, "AWAY_OVER_UNDER_2_5_PROBABILITY", "客队大小球2.5",
     {"yes": 21.0, "no": 79.0}),
    (330, "HOME_OVER_UNDER_2_5_PROBABILITY", "主队大小球2.5",
     {"yes": 20.0, "no": 80.0}),
    (331, "HOME_OVER_UNDER_1_5_PROBABILITY", "主队大小球1.5",
     {"yes": 42.0, "no": 58.0}),
    (332, "AWAY_OVER_UNDER_1_5_PROBABILITY", "客队大小球1.5",
     {"yes": 45.0, "no": 55.0}),
    (333, "AWAY_OVER_UNDER_0_5_PROBABILITY", "客队大小球0.5",
     {"yes": 74.0, "no": 26.0}),
    (334, "HOME_OVER_UNDER_0_5_PROBABILITY", "主队大小球0.5",
     {"yes": 71.0, "no": 29.0}),
    (1679, "OVER_UNDER_4_5_PROBABILITY", "大小球4.5", {"yes": 24.0, "no": 76.0}),
    (1683, "CORNERS_OVER_UNDER_5_PROBABILITY", "角球大小5",
     {"yes": 90.0, "no": 5.0, "equal": 5.0}),
    (1685, "CORNERS_OVER_UNDER_6_PROBABILITY", "角球大小6",
     {"yes": 84.0, "no": 9.0, "equal": 7.0}),
    (1686, "CORNERS_OVER_UNDER_7_PROBABILITY", "角球大小7",
     {"yes": 75.0, "no": 16.0, "equal": 9.0}),
    (1687, "CORNERS_OVER_UNDER_9_PROBABILITY", "角球大小9",
     {"yes": 54.0, "no": 34.0, "equal": 12.0}),
    (1689, "CORNERS_OVER_UNDER_8_PROBABILITY", "角球大小8",
     {"yes": 65.0, "no": 24.0, "equal": 11.0}),
    (1690, "CORNERS_OVER_UNDER_4_PROBABILITY", "角球大小4",
     {"yes": 95.0, "no": 2.0, "equal": 3.0}),
]


def _kickoff_utc_value(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=CN_TZ).astimezone(UTC).replace(tzinfo=None)


def _seed_match(db, kickoff: str):
    db.merge(SPMatch(
        match_id="board-1", match_no="周四901", league="欧国联",
        home_raw="主队", away_raw="客队", home="主队", away="客队",
        kickoff=kickoff, single_flag=True))
    db.merge(SportmonksMatchData(
        match_id="board-1", fixture_id=99001, league="欧国联",
        home_name="主队", away_name="客队",
        kickoff_utc="2026-11-13 13:00:00", captured_at=utcnow()))
    for type_id, code, name, probabilities in _PREDICTIONS:
        db.merge(SportmonksPrediction(
            match_id="board-1", type_id=type_id, type_code=code,
            type_name=name, probabilities=probabilities, captured_at=utcnow()))
    db.merge(Verdict(
        id="v-board-1", trade_date=today_cn(), match_id="board-1",
        match_no="周四901", league="欧国联", home="主队", away="客队",
        kickoff=kickoff, pool="had", goal_line="", sp_h=2.1, sp_d=3.2,
        sp_a=3.4, rake=0.09, p_home=0.45, p_draw=0.3, p_away=0.25,
        pick={"dir": "客胜", "prob": 0.25, "sp": 3.4},
        status="screening", tier="market_reference",
        gates={"price": {"result": "pass"}},
        payload={"model": {"shrunk": [0.45, 0.30, 0.25]}},
        payload_hash="a" * 64))
    db.commit()


def test_prediction_snapshot_locks_once_and_settles_all_dimensions(db):
    kickoff = future_kickoff(today_cn(), hour=23, minute=59)
    _seed_match(db, kickoff)
    before = _kickoff_utc_value(kickoff) - timedelta(minutes=30)
    opened = service.freeze_prediction_snapshots(db, now=before)
    assert opened["opened"] == 1
    snapshot = db.get(SportmonksPredictionSnapshot, "board-1")
    assert snapshot is not None and snapshot.locked_at is None
    assert len(snapshot.predictions) == 25

    after = _kickoff_utc_value(kickoff) + timedelta(minutes=1)
    locked = service.freeze_prediction_snapshots(db, now=after)
    assert locked["locked"] == 1
    assert snapshot.locked_at is not None
    frozen_predictions = list(snapshot.predictions)
    # 再次冻结不能改动已锁定内容。
    service.freeze_prediction_snapshots(db, now=after + timedelta(hours=1))
    assert snapshot.predictions == frozen_predictions

    result = MatchResult(
        source="sportmonks", league="欧国联", home_raw="主队", away_raw="客队",
        home="主队", away="客队", match_date=kickoff[:10], fixture_id=99001,
        status="FT", ft_home=2, ft_away=1, ht_home=1, ht_away=0,
        goals_home=2, goals_away=1, retrieved_at=utcnow().isoformat())
    db.add(result)
    db.flush()
    db.add(MatchResultDetail(
        result_id=result.id, fixture_id=99001,
        actuals=service.parse_actuals({
            "state": {"short_name": "FT"},
            "scores": [
                {"score": {"participant": "home", "goals": 1},
                 "description": "1ST_HALF"},
                {"score": {"participant": "away", "goals": 0},
                 "description": "1ST_HALF"},
                {"score": {"participant": "home", "goals": 2},
                 "description": "2ND_HALF"},
                {"score": {"participant": "away", "goals": 1},
                 "description": "2ND_HALF"},
                {"score": {"participant": "home", "goals": 2},
                 "description": "CURRENT"},
                {"score": {"participant": "away", "goals": 1},
                 "description": "CURRENT"},
            ],
            "statistics": [
                {"type": {"developer_name": "CORNERS"},
                 "location": "home", "data": {"value": 4}},
                {"type": {"developer_name": "CORNERS"},
                 "location": "away", "data": {"value": 3}},
            ],
            "events": [
                {"type_id": 14, "participant_id": 10, "minute": 20, "id": 1},
                {"type_id": 14, "participant_id": 20, "minute": 70, "id": 2},
            ],
            "participants": [
                {"id": 10, "name": "主队", "meta": {"location": "home"}},
                {"id": 20, "name": "客队", "meta": {"location": "away"}},
            ],
        })))
    db.commit()
    settled = service.settle_prediction_snapshots(db)
    assert settled["settled"] == 1
    rows = db.scalars(select(SportmonksPredictionSettlement).where(
        SportmonksPredictionSettlement.match_id == "board-1")).all()
    assert len(rows) == 26
    counted = [row for row in rows if row.counted_in_accuracy]
    assert {row.prediction_type for row in counted} == {
        "product_main", "OVER_UNDER_2_5_PROBABILITY", "BTTS_PROBABILITY"}
    assert all(row.result in ("hit", "miss", "push") for row in counted)
    corners = next(row for row in rows
                   if row.prediction_type == "CORNERS_OVER_UNDER_5_PROBABILITY")
    assert corners.actual_key == "over" and corners.result == "hit"
    assert not corners.counted_in_accuracy
    history = service.build_prediction_history(db, kickoff[:10])
    assert history["count"] == 1
    assert history["matches"][0]["score_home"] == 2
    assert history["matches"][0]["score_away"] == 1
    assert history["matches"][0]["main_prediction"]["direction"] == "主胜"
    assert history["matches"][0]["main_prediction"]["probability"] == 0.45
    assert history["summary"]["settled_items"] == 3
    detail = service.build_prediction_history_detail(db, "board-1")
    assert detail is not None and len(detail["items"]) == 26
    assert detail["score_home"] == 2 and detail["score_away"] == 1
    assert detail["half_check"] == {
        "predicted_ht": "主胜", "actual_ht": "主胜", "on_track": True}
    labels = {item["type"]: item["predicted_label"] for item in detail["items"]}
    assert labels["product_main"] == "主胜"
    product = next(item for item in detail["items"]
                   if item["type"] == "product_main")
    assert product["predicted_probability"] == 0.45
    assert [row["key"] for row in product["probabilities"]] == [
        "home", "draw", "away"]
    assert product["probabilities"][0]["probability"] == 0.45
    assert labels["OVER_UNDER_2_5_PROBABILITY"] == "大 2.5"
    assert labels["CORNERS_OVER_UNDER_5_PROBABILITY"] == "大 5"
    htft = next(item for item in detail["items"]
                if item["type"] == "HTFT_PROBABILITY")
    assert htft["actual_label"] == "主胜/主胜"
    assert htft["actual_key"] == "home_home"
    fulltime = next(item for item in detail["items"]
                    if item["type"] == "FULLTIME_RESULT_PROBABILITY")
    assert len(fulltime["probabilities"]) == 3
    assert fulltime["probabilities"][0]["probability"] == 0.4
    correct_detail = next(item for item in detail["items"]
                          if item["type"] == "CORRECT_SCORE_PROBABILITY")
    assert len(correct_detail["probabilities"]) == 4
    assert correct_detail["probabilities"][0]["key"] == "Other_1"
    assert correct_detail["probabilities"][0]["probability"] == 0.2
    # 概率最高的 1-1 与实际 2-1 不一致，仍要展示对照。
    correct = next(row for row in rows
                   if row.prediction_type == "CORRECT_SCORE_PROBABILITY")
    assert correct.predicted_key == "1-1" and correct.result == "miss"


def test_performance_dashboard_aggregates_settlements(db):
    kickoff = future_kickoff(today_cn(), hour=23, minute=59)
    _seed_match(db, kickoff)
    before = _kickoff_utc_value(kickoff) - timedelta(minutes=30)
    service.freeze_prediction_snapshots(db, now=before)
    service.freeze_prediction_snapshots(db, now=_kickoff_utc_value(kickoff) + timedelta(minutes=1))
    result = MatchResult(
        source="sportmonks", league="欧国联", home_raw="主队", away_raw="客队",
        home="主队", away="客队", match_date=kickoff[:10], fixture_id=99001,
        status="FT", ft_home=2, ft_away=1, ht_home=1, ht_away=0,
        goals_home=2, goals_away=1, retrieved_at=utcnow().isoformat())
    db.add(result)
    db.flush()
    db.add(MatchResultDetail(
        result_id=result.id, fixture_id=99001,
        actuals=service.parse_actuals({
            "state": {"short_name": "FT"},
            "scores": [
                {"score": {"participant": "home", "goals": 2}, "description": "2ND_HALF"},
                {"score": {"participant": "away", "goals": 1}, "description": "2ND_HALF"},
            ],
        })))
    db.commit()
    service.settle_prediction_snapshots(db)

    perf = service.build_performance(db, days=30)
    assert perf["total_settled"] == 3
    assert perf["hit_rate"] is not None
    assert len(perf["trend"]) >= 1
    markets = {row["market"] for row in perf["by_market"]}
    assert "主预测" in markets and "大小球" in markets and "双方进球" in markets
    calibration = {row["bucket"] for row in perf["calibration"]}
    assert calibration  # 至少一个桶有数据


def test_live_and_result_boards_do_not_expose_predictions(db, client):
    kickoff = future_kickoff(today_cn(), hour=23, minute=59)
    _seed_match(db, kickoff)
    db.merge(SportmonksLiveState(
        match_id="board-1", fixture_id=99001, state_short="2H", minute="72",
        score_home=1, score_away=1, ht_home=0, ht_away=1))
    db.commit()

    live = client.get("/matches/live").json()
    assert live["count"] == 1
    row = live["matches"][0]
    assert row["match_id"] == "board-1"
    assert "prediction" not in row and "pick" not in row
    assert row["state"] == "2H" and row["minute"] == "72"

    result = MatchResult(
        source="sportmonks", league="欧国联", home_raw="主队", away_raw="客队",
        home="主队", away="客队", match_date=kickoff[:10], fixture_id=99001,
        status="FT", ft_home=2, ft_away=1, ht_home=1, ht_away=0,
        goals_home=2, goals_away=1, retrieved_at=utcnow().isoformat())
    db.add(result)
    db.commit()
    finished = client.get("/matches/results", params={"date": kickoff[:10]}).json()
    assert finished["count"] == 1
    assert finished["matches"][0]["score_home"] == 2
    assert "prediction" not in finished["matches"][0]


def test_sync_live_states_parses_inplay_and_period_minute(db, monkeypatch):
    kickoff = future_kickoff(today_cn(), hour=23, minute=59)
    _seed_match(db, kickoff)
    payload = {"data": [{
        "id": 99001,
        "state": {"short_name": "2H"},
        "scores": [
            {"score": {"participant": "home", "goals": 1}, "description": "CURRENT"},
            {"score": {"participant": "away", "goals": 1}, "description": "CURRENT"},
            {"score": {"participant": "home", "goals": 0}, "description": "1ST_HALF"},
            {"score": {"participant": "away", "goals": 1}, "description": "1ST_HALF"},
        ],
        "periods": [{"sort_order": 2, "minutes": 67}],
    }]}
    monkeypatch.setattr(service, "_get", lambda *args, **kwargs: payload)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        sportmonks_token="test", sportmonks_base_url="http://sportmonks.test"))
    message = service.sync_live_states(db, force=True)
    assert "live 1/1" in message
    state = db.get(SportmonksLiveState, "board-1")
    assert state is not None
    assert state.state_short == "2H" and state.minute == "67"
    assert state.score_home == 1 and state.score_away == 1
    assert state.ht_home == 0 and state.ht_away == 1


def test_market_lines_prefer_sporttery_ttg_over_sportmonks(db):
    _seed_match(db, future_kickoff(today_cn(), hour=23, minute=59))
    db.add(SportmonksMarket(match_id="board-1", market_key="ou", line="2.5"))
    db.add(SPPoolSnapshot(
        match_id="board-1", pool="ttg", line="", captured_at="2026-11-13 10:00:00",
        selections={"s0": "32.00", "s1": "9.35", "s2": "5.40", "s3": "4.40",
                    "s4": "4.15", "s5": "5.25", "s6": "7.50", "s7": "7.25"}))
    db.commit()
    lines = service._market_lines(db, ["board-1"])
    assert lines["board-1"]["ou"] == "4.5"
    assert lines["board-1"]["ou_source"] == "sporttery_ttg_implied"


def test_implied_ou_line_follows_sporttery_total_goals():
    selections = {"s0": "32.00", "s1": "9.35", "s2": "5.40", "s3": "4.40",
                  "s4": "4.15", "s5": "5.25", "s6": "7.50", "s7": "7.25"}
    assert service._implied_ou_line(selections) == "4.5"
    assert service._implied_ou_line({}) == ""


def test_product_actual_uses_real_outcome_not_predicted_key():
    snapshot = SimpleNamespace(
        product_pick={"dir": "主胜"}, market_lines={"product_pool": "hhad",
                                                     "product_line": "-1"})
    assert service._product_actual(snapshot, {
        "ft_home": 2, "ft_away": 1, "ft_outcome": "home"}, "主胜") == ("draw", "让球平")
    snapshot.market_lines = {"product_pool": "had", "product_line": ""}
    assert service._product_actual(snapshot, {
        "ft_home": 2, "ft_away": 1, "ft_outcome": "home"}, "主胜") == ("home", "主胜")


def test_result_board_prioritizes_interested_match_without_label(db):
    day = today_cn()
    rows = [("board-early", "周四902", f"{day} 19:00:00", 191),
            ("board-late", "周四903", f"{day} 21:00:00", 192)]
    for match_id, match_no, kickoff, fixture_id in rows:
        db.merge(SPMatch(
            match_id=match_id, match_no=match_no, league="欧国联",
            home_raw=f"{match_id}-主", away_raw=f"{match_id}-客",
            home=f"{match_id}-主", away=f"{match_id}-客",
            kickoff=kickoff, single_flag=False))
        db.merge(SportmonksMatchData(
            match_id=match_id, fixture_id=fixture_id,
            league="欧国联", home_name=f"{match_id}-主",
            away_name=f"{match_id}-客", kickoff_utc="", captured_at=utcnow()))
        db.add(MatchResult(
            source="sportmonks", league="欧国联",
            home_raw=f"{match_id}-主", away_raw=f"{match_id}-客",
            home=f"{match_id}-主", away=f"{match_id}-客",
            match_date=day, fixture_id=fixture_id,
            status="FT", ft_home=1, ft_away=0, ht_home=0, ht_away=0,
            goals_home=1, goals_away=0, retrieved_at=utcnow().isoformat()))
    user = User(id="u-board", device_token="dev-board", display_name="测试")
    db.add(user)
    db.add(WatchTarget(user_id=user.id, target_type="match",
                       target_id="board-early"))
    db.commit()

    anonymous = service.build_result_board(db, day)
    assert [row["match_id"] for row in anonymous["matches"]] == [
        "board-late", "board-early"]
    personalized = service.build_result_board(db, day, user=user)
    assert [row["match_id"] for row in personalized["matches"]] == [
        "board-early", "board-late"]
    assert personalized["matches"][0]["interest"] is True
    assert "watched" not in personalized["matches"][0]


def test_parse_actuals_own_goal_opener_side():
    """乌龙球开纪录：participant 是防守方，进球方按累计比分推导。"""
    from app.features.board import service as board_service
    fixture = {
        "state": {"short_name": "FT"},
        "participants": [
            {"id": 10, "name": "主队", "meta": {"location": "home"}},
            {"id": 20, "name": "客队", "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": "1ST_HALF", "score": {"participant": "home", "goals": 0}},
            {"description": "1ST_HALF", "score": {"participant": "away", "goals": 1}},
            {"description": "2ND_HALF", "score": {"participant": "home", "goals": 0}},
            {"description": "2ND_HALF", "score": {"participant": "away", "goals": 2}},
            {"description": "CURRENT", "score": {"participant": "home", "goals": 0}},
            {"description": "CURRENT", "score": {"participant": "away", "goals": 3}},
        ],
        "events": [
            # 乌龙球开纪录：participant 10（主队/防守方），累计比分 0-1 → 进球方是客队
            {"type_id": 15, "participant_id": 10, "minute": 12,
             "player": {"name": "乌龙后卫"}, "result": "0-1"},
            {"type_id": 14, "participant_id": 20, "minute": 55,
             "player": {"name": "客队前锋"}, "result": "0-2"},
            {"type_id": 14, "participant_id": 20, "minute": 70,
             "player": {"name": "客队前锋"}, "result": "0-3"},
        ],
        "statistics": [],
    }
    actuals = board_service.parse_actuals(fixture)
    assert actuals["first_goal_side"] == "away"


def test_parse_actuals_penalty_opener_side():
    """点球开纪录（type_id=16）也计入先进球。"""
    from app.features.board import service as board_service
    fixture = {
        "state": {"short_name": "FT"},
        "participants": [
            {"id": 10, "name": "主队", "meta": {"location": "home"}},
            {"id": 20, "name": "客队", "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": "1ST_HALF", "score": {"participant": "home", "goals": 1}},
            {"description": "1ST_HALF", "score": {"participant": "away", "goals": 0}},
            {"description": "2ND_HALF", "score": {"participant": "home", "goals": 0}},
            {"description": "2ND_HALF", "score": {"participant": "away", "goals": 0}},
            {"description": "CURRENT", "score": {"participant": "home", "goals": 1}},
            {"description": "CURRENT", "score": {"participant": "away", "goals": 0}},
        ],
        "events": [
            {"type_id": 16, "participant_id": 10, "minute": 8,
             "player": {"name": "主队点球手"}, "result": "1-0"},
        ],
        "statistics": [],
    }
    actuals = board_service.parse_actuals(fixture)
    assert actuals["first_goal_side"] == "home"
