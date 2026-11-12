"""v4.1 core: 90-minute settlement / 4-match plan / membership."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (MatchResult, PlanBet, PlanBetLeg, PlanCycle, User,
                        Verdict)
from app.modules import membership, plan_service, settlement
from app.modules.timeutil import CN, trade_date_now
from tests.conftest import admin_login

CN_TZ = timezone(timedelta(hours=8))


def _verdict(idx: int, kickoff: str, league: str = "英超") -> Verdict:
    return Verdict(
        id=f"v4-test-{idx}", trade_date=trade_date_now(), match_id=f"m4-{idx}",
        match_no=f"周四{idx:03d}", league=league, home=f"主队{idx}",
        away=f"客队{idx}", kickoff=kickoff, pool="had", goal_line="",
        sp_h=1.92, sp_d=3.50, sp_a=4.10, rake=0.09,
        p_home=0.52, p_draw=0.25, p_away=0.23,
        model_h=0.57, model_d=0.24, model_a=0.19,
        pick={"dir": "主胜", "sp": 1.92, "prob": 0.57},
        rake_threshold=0.13, status="promoted", tier="verified",
        model_status="enabled", model_source="dc",
        gates={"price": {"result": "pass"}, "market": {"result": "pass"},
               "model": {"result": "pass"}},
        payload={"model": {"engine": "dc-v1.1"}},
        payload_hash=f"{idx:064d}", sealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def _kickoff(days: int = 1, hour: int = 20) -> str:
    base = datetime.now(CN_TZ) + timedelta(days=days)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S")


def test_90min_outcome_does_not_use_aet():
    assert settlement.outcome("had", "", "主胜", (2, 1)) == ("home", True)
    assert settlement.outcome("had", "", "主胜", (1, 1)) == ("draw", False)
    assert settlement.outcome("hhad", "-1", "主胜", (2, 1)) == ("draw", False)
    assert settlement.outcome("hhad", "-1", "主胜", (3, 1)) == ("home", True)
    assert settlement.outcome("ou", "2.5", "大", (2, 1)) == ("over", True)
    assert settlement.outcome("btts", "", "是", (1, 0)) == ("no", False)
    # 整数大小球走水：不是赢，也不是输。
    assert settlement.outcome("ou", "3", "大", (2, 1)) == ("push", None)


def test_build_stable_cycle_and_membership(db, client):
    date = trade_date_now()
    for i in range(1, 5):
        db.add(_verdict(i, _kickoff(1, 18 + i), "英超" if i < 3 else "西甲"))
    db.commit()
    cycle = plan_service.build_cycle(db, "stable", date=date)
    assert cycle is not None
    bets = list(db.scalars(select(PlanBet).where(PlanBet.cycle_id == cycle.id)).all())
    legs = list(db.scalars(select(PlanBetLeg).where(
        PlanBetLeg.bet_id.in_([b.id for b in bets]))).all())
    assert len(bets) == 4
    assert len(legs) == 4
    assert cycle.total_stake == 400
    assert all(b.bet_type == "single" for b in bets)

    # 免费：当前期锁定，不返回 legs
    free = client.get("/plans/current?risk=stable")
    assert free.status_code == 200
    assert free.json()["locked"] is True
    assert free.json()["plan"]["bets"] == []

    user = User(id="u-v4", device_token="dev-v4", display_name="v4")
    db.add(user)
    db.commit()
    membership.grant(db, user.id, "max", 30, actor="test")
    paid = client.get("/plans/current?risk=stable",
                      headers={"Authorization": "Bearer dev-v4"})
    assert paid.status_code == 200
    assert paid.json()["locked"] is False
    bets = paid.json()["plan"]["bets"]
    assert len(bets) == 4
    first_leg = bets[0]["legs"][0]
    assert first_leg["home"] == "主队1"
    assert first_leg["away"] == "客队1"
    assert first_leg["direction"] == "主胜"


def test_settle_cycle_after_result(db):
    date = trade_date_now()
    for i in range(1, 3):
        db.add(_verdict(i, _kickoff(1, 18 + i)))
    db.commit()
    cycle = plan_service.build_cycle(db, "stable", date=date)
    assert cycle is not None
    # 两场都赢；结果表的 match_date 用 kickoff 前一天/当天窗口，直接按当前日期建。
    v = db.scalar(select(Verdict).where(Verdict.id == "v4-test-1"))
    result = MatchResult(
        source="test", league=v.league, home=v.home, away=v.away,
        home_raw=v.home, away_raw=v.away, match_date=v.kickoff[:10],
        status="FT", ft_home=2, ft_away=1, goals_home=2, goals_away=1,
    )
    db.add(result)
    db.commit()
    assert settlement.settle_verdict(db, v, result) == 1
    v2 = db.scalar(select(Verdict).where(Verdict.id == "v4-test-2"))
    result2 = MatchResult(
        source="test", league=v2.league, home=v2.home, away=v2.away,
        home_raw=v2.home, away_raw=v2.away, match_date=v2.kickoff[:10],
        status="FT", ft_home=3, ft_away=0, goals_home=3, goals_away=0,
    )
    db.add(result2)
    db.commit()
    assert settlement.settle_verdict(db, v2, result2) == 1
    db.commit()
    assert v.settled == "win"
    plan_service.settle_cycle(db, cycle)
    db.refresh(cycle)
    assert cycle.status == "settled"
    assert cycle.pnl > 0


def test_engine_uptime_and_market_access(db, client):
    user = User(id="u-engine", device_token="dev-engine", display_name="e")
    user.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
    db.add(user)
    db.commit()
    r = client.get("/stats/engine", headers={"Authorization": "Bearer dev-engine"})
    assert r.status_code == 200
    assert r.json()["uptime_hours"] == 5
    assert r.json()["version"] == "V3.21"
    assert membership.market_allowed(db, "pro", "hhad") is True
    assert membership.market_allowed(db, "pro", "ou") is False
    assert membership.market_allowed(db, "max", "ou") is True


def test_chat_persona_and_record_intent(client):
    res = client.post("/chat", json={"text": "最近准吗", "persona": "laopao"})
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "record"
    assert data["persona"] == "laopao"
    assert "兄弟" in data["text"] or "战绩" in data["text"]


def test_plan_ignores_past_kickoff(db):
    db.add(_verdict(9, _kickoff(-1)))
    db.commit()
    assert plan_service.build_cycle(db, "stable", date=trade_date_now()) is None


def test_verdict_detail_exposes_match_id(client, db):
    v = _verdict(99, _kickoff(1, 20))
    db.add(v)
    db.commit()
    response = client.get(f"/verdicts/{v.id}")
    assert response.status_code == 200
    assert response.json()["match_id"] == "m4-99"


def test_workbench_push_reports_dry_run_without_server_keys(client, monkeypatch):
    monkeypatch.delenv("JQ_JPUSH_APPKEY", raising=False)
    monkeypatch.delenv("JQ_JPUSH_MASTER_SECRET", raising=False)
    admin_login(client)
    payload = client.get("/admin/api/workbench")
    assert payload.status_code == 200
    push = next(stage for stage in payload.json()["stages"] if stage["key"] == "push")
    assert "dry-run" in push["headline"]
    assert push["state"] in ("warn", "blocked")
