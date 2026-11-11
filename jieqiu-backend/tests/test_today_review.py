"""2026-11-11 深审回归：概率卡模型字段、市场新鲜度、SM 日期窗口、情报过期。"""
from datetime import datetime, timedelta

from app.models import AIResearch, SPMatch, SportmonksMatchData, Verdict, utcnow
from app.modules.sportmonks import _fixture_date_range, market_is_fresh
from tests.conftest import future_kickoff, today_cn


def _verdict(db, mid="review-1", **overrides):
    kickoff = future_kickoff(today_cn())
    db.merge(SPMatch(match_id=mid, match_no="周五995", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    data = dict(
        id=f"v-{mid}", trade_date=today_cn(), match_id=mid, match_no="周五995",
        league="英超", home="曼城", away="曼联", kickoff=kickoff,
        pool="had", goal_line="", sp_h=2.10, sp_d=3.40, sp_a=3.30,
        rake=0.10, p_home=0.45, p_draw=0.29, p_away=0.26,
        model_h=0.58, model_d=0.24, model_a=0.18,
        pick={"dir": "主胜", "prob": 0.58, "sp": 2.10}, rake_threshold=0.13,
        status="promoted", gates={}, payload={}, payload_hash="a" * 64,
    )
    data.update(overrides)
    db.merge(Verdict(**data))
    db.commit()
    return data


def test_probability_compare_uses_model_fields_not_market(client, db):
    _verdict(db, mid="review-model")
    body = client.get("/verdicts/v-review-model").json()
    compare = body["probability_compare"]
    assert compare["model_enabled"] is True
    assert compare["model"]["home"] == 0.58
    assert compare["model"]["draw"] == 0.24
    assert compare["model"]["away"] == 0.18
    # 竞彩去水仍是独立一行，不能被模型覆盖。
    assert compare["sp"]["home"] != compare["model"]["home"]


def test_market_freshness_rejects_stale_odds(db):
    kick = future_kickoff(today_cn())
    stale = SportmonksMatchData(
        match_id="stale-1", fixture_id=1, odds={"home": 0.5, "draw": 0.3, "away": 0.2},
        captured_at=utcnow() - timedelta(hours=3))
    fresh = SportmonksMatchData(
        match_id="fresh-1", fixture_id=2, odds={"home": 0.5, "draw": 0.3, "away": 0.2},
        captured_at=utcnow())
    assert market_is_fresh(stale) is False
    assert market_is_fresh(fresh) is True
    assert market_is_fresh(None) is False


def test_sportmonks_fixture_range_converts_cn_to_utc():
    # 11-11 05:00 CN 已是 11-10 21:00 UTC，必须从 UTC 前一天开始拉。
    assert _fixture_date_range("2026-11-11 05:00:00",
                               "2026-11-12 04:59:59") == ("2026-11-10", "2026-11-11")


def test_ai_research_expiry_is_hidden(client, db):
    _verdict(db, mid="review-intel")
    db.merge(AIResearch(match_id="review-intel", status="ready",
                        headline="旧情报", points=["旧要点"],
                        captured_at=utcnow() - timedelta(hours=7),
                        expires_at=utcnow() - timedelta(hours=1)))
    db.commit()
    body = client.get("/verdicts/v-review-intel").json()
    assert body["ai_research"]["status"] == "expired"
    assert body["ai_research"]["headline"] == "旧情报"


def test_snapshot_preserves_last_good_data_and_clears_on_remap(db):
    from app.modules.sportmonks import _snapshot

    kickoff = future_kickoff(today_cn())
    mid = "snapshot-1"
    db.merge(SPMatch(match_id=mid, match_no="周五996", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    db.commit()
    match = db.get(SPMatch, mid)
    fixture = {"id": 1001, "starting_at": kickoff, "participants": [
        {"name": "曼城", "meta": {"location": "home"}},
        {"name": "曼联", "meta": {"location": "away"}},
    ], "league": {"name": "英超"}}
    row = _snapshot(db, match, fixture, {"home": 0.5, "draw": 0.3, "away": 0.2},
                    {"home": 0.52, "draw": 0.28, "away": 0.2}, "Pinnacle", "sportmonks")
    db.commit()
    old_cutoff = row.captured_at
    row.source = "manual"

    same = _snapshot(db, match, fixture, None, None, "", "sportmonks")
    assert same.source == "manual"
    assert same.probs == {"home": 0.5, "draw": 0.3, "away": 0.2}
    assert same.captured_at == old_cutoff

    moved = _snapshot(db, match, {**fixture, "id": 2002}, None, None, "",
                      "sportmonks")
    assert moved.fixture_id == 2002
    assert moved.probs is None
    assert moved.odds is None


def test_supply_market_scope_only_upcoming(db):
    from datetime import timedelta
    from app.modules.supply import content_supply
    from app.modules.timeutil import CN

    kickoff = (datetime.now(CN) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    db.merge(SPMatch(match_id="past-market-1", match_no="周五999", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    db.commit()
    supply = content_supply(db, today_cn())
    assert supply["upcoming_matches"] == 0
    assert supply["market_covered_matches"] == 0
    assert "市场" not in (supply["blocked_reason"] or "")
