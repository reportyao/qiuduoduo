"""内容供给诊断：国际盘缺失时，主链为什么不会产出 published。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.features.recommendations import service
from app.models import IntlOdds, SPMatch, TeamAlias, Verdict
from app.modules.align import normalize, seed_aliases
from app.modules.intl_odds import sports_for_trade_date
from app.modules.supply import content_supply
from tests.conftest import CN, admin_login, today_cn
from tests.test_recommendations import _seed, _seed_market


def test_supply_reports_market_starvation(client, db):
    _seed_market(db, "sup-1", "周三991")
    _seed(db, mid="sup-1", no="周三991")
    v = db.get(Verdict, "v-sup-1")
    v.status = "screening"
    v.gates = {"price": {"result": "pass"},
               "market": {"result": "pending_data"},
               "model": {"result": "pending_data"}}
    db.commit()

    data = content_supply(db)
    assert data["matches"] == 1
    assert data["verdicts"]["total"] == 1
    assert data["market_gate"]["pending_data"] == 1
    assert data["intl_odds"]["total"] == 0
    assert data["intl_odds"]["configured"] is False
    assert data["published"] == 0
    assert "国际盘" in (data["blocked_reason"] or "")

    msg = client.get("/recommendations/today").json()["message"]
    assert "稍后" in msg


def test_supply_counts_covered_intl_source(db):
    _seed_market(db, "sup-2", "周三992")
    match = db.get(SPMatch, "sup-2")
    kickoff_cn = datetime.strptime(match.kickoff, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
    db.add(IntlOdds(
        source="pinnacle", sport="soccer_epl", league="英超",
        home_raw="Manchester City", away_raw="Manchester United",
        home=match.home, away=match.away,
        kickoff_utc=kickoff_cn.astimezone(timezone.utc).isoformat(timespec="seconds"),
        sp_h=1.80, sp_d=3.50, sp_a=4.20,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    ))
    db.commit()

    data = content_supply(db)
    assert data["intl_odds"]["total"] == 1
    assert data["intl_odds"]["covered_matches"] == 1
    assert data["intl_odds"]["missing_matches"] == 0


def test_admin_data_exposes_supply(client, db):
    admin_login(client)
    body = client.get("/admin/api/data").json()
    assert "supply" in body
    for key in ("matches", "market_gate", "intl_odds", "blocked_reason", "published"):
        assert key in body["supply"]


def test_supply_excludes_expired_published(db):
    _seed_market(db, "sup-3", "周三993")
    _seed(db, mid="sup-3", no="周三993")
    snap = service.build_snapshots(db, today_cn())[0]
    service.review_subject(db, service.SUBJECT_DECISION, snap.id)
    service.publish_subject(db, service.SUBJECT_DECISION, snap.id)
    snap.expires_at = datetime.now(CN).replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()

    data = content_supply(db)
    assert data["snapshots"]["published"] == 0
    assert data["published"] == 0
    assert "国际盘" in (data["blocked_reason"] or "")


def test_sports_for_trade_date_maps_european_leagues(db):
    _seed_market(db, "sup-4", "周四001")
    match = db.get(SPMatch, "sup-4")
    match.league = "欧罗巴联赛"
    db.merge(SPMatch(match_id="sup-5", match_no="周四002", league="欧协联",
                     home_raw="A", away_raw="B", home="A", away="B",
                     kickoff=match.kickoff, single_flag=False))
    db.merge(SPMatch(match_id="sup-6", match_no="周四003", league="欧国联",
                     home_raw="C", away_raw="D", home="C", away="D",
                     kickoff=match.kickoff, single_flag=False))
    db.commit()

    sports = sports_for_trade_date(db)
    assert "soccer_uefa_europa_league" in sports
    assert "soccer_uefa_europa_conference_league" in sports
    assert "soccer_uefa_nations_league" in sports


def test_seed_aliases_backfills_new_european_names(db):
    db.add(TeamAlias(alias="keep-me", canonical="保留"))
    db.commit()
    added = seed_aliases(db)
    assert added > 0
    row = db.query(TeamAlias).filter_by(alias=normalize("Lyon")).one()
    assert row.canonical == "里昂"
    row = db.query(TeamAlias).filter_by(alias=normalize("Crystal Palace")).one()
    assert row.canonical == "水晶宫"
