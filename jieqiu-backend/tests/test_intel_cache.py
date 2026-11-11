"""AI 情报缓存：事实不变时不重复调用 LLM。"""
from app.models import AIResearch, SPMatch, SportmonksMatchData
from app.modules import intel_research
from tests.conftest import future_kickoff, today_cn


def test_intel_sync_reuses_cached_summary_when_facts_unchanged(db, monkeypatch):
    mid = "intel-cache-1"
    kickoff = future_kickoff(today_cn())
    db.merge(SPMatch(match_id=mid, match_no="周五997", league="英超",
                     home_raw="曼城", away_raw="曼联", home="曼城", away="曼联",
                     kickoff=kickoff, single_flag=True))
    db.merge(SportmonksMatchData(
        match_id=mid, fixture_id=770001, league="英超",
        home_name="曼城", away_name="曼联", kickoff_utc=kickoff,
        probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        odds={"home": 0.52, "draw": 0.28, "away": 0.2},
        bookmaker="Pinnacle", data_cutoff="2026-11-11T12:00:00"))
    db.commit()

    facts = {"value": ["曼城近 5 场 4 胜", "曼联两名主力伤停"]}
    calls = []

    def fake_fetch(_fixture_id):
        return list(facts["value"]), 2

    def fake_summarize(_db, items, injured):
        calls.append((list(items), injured))
        return "中文摘要", ["要点"]

    monkeypatch.setattr(intel_research, "_fetch", fake_fetch)
    monkeypatch.setattr(intel_research, "_summarize", fake_summarize)

    assert intel_research.sync_match(db, mid) is True
    assert len(calls) == 1
    row = db.get(AIResearch, mid)
    assert row.status == "ready"
    assert row.facts_hash
    first_cutoff = row.captured_at

    # 事实不变：不再调用 LLM，只续期。
    assert intel_research.sync_match(db, mid) is True
    assert len(calls) == 1
    db.expire_all()
    row = db.get(AIResearch, mid)
    assert row.captured_at >= first_cutoff
    assert row.facts_hash

    # 事实变化：重新调用一次。
    facts["value"] = ["曼城新增一名伤停"]
    assert intel_research.sync_match(db, mid) is True
    assert len(calls) == 2
