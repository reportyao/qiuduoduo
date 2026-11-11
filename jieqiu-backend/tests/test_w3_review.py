"""W3 Review 修复回归：intl upsert / 同源去重 / 让球口径 / 避雷收编 / 详情字段。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import Settings
from app.models import IntlOdds, SPMatch, SPSnapshot, SportmonksMatchData
from app.modules import verdict as vz
from app.modules.align import Aligner, seed_aliases
from app.modules.dc_model import fit, predict, predict_line
from app.modules.intl_odds import sync_the_odds_api
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


def _fake_events(sp=(1.42, 4.50, 6.80)):
    def _f(sport):
        if sport != "soccer_epl":
            return []
        return [{
            "id": "e1", "sport_key": sport, "sport_title": "EPL",
            "commence_time": "2026-11-03T12:55:00Z",
            "home_team": "DOMINATOR", "away_team": "WEAK",
            "bookmakers": [{"key": "pinnacle", "title": "Pinnacle",
                            "markets": [{"key": "h2h", "outcomes": [
                                {"name": "DOMINATOR", "price": sp[0]},
                                {"name": "Draw", "price": sp[1]},
                                {"name": "WEAK", "price": sp[2]}]}]}],
        }]
    return _f


def test_intl_sync_upsert_no_crash(db, monkeypatch):
    """修复1：第二次同步同一场 → 更新而非撞唯一键。"""
    monkeypatch.setattr("app.modules.intl_odds.get_settings", vz.get_settings)  # 对齐节流配置
    # 节流基于 IntlOdds.retrieved_at；首次为空 → 不节流
    n1, _ = sync_the_odds_api(db, Aligner(db), datetime.now(timezone.utc),
                              api_key="test", fetch_events=_fake_events())
    assert n1 == 1
    # 6h 节流会挡第二次 → 把行 retrieved_at 拨回 7h 前
    row = db.scalar(select(IntlOdds))
    row.retrieved_at = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(timespec="seconds")
    db.commit()
    n2, note = sync_the_odds_api(db, Aligner(db), datetime.now(timezone.utc),
                                 api_key="test", fetch_events=_fake_events((1.50, 4.20, 6.20)))
    assert n2 == 1  # 更新而非插入
    assert db.query(IntlOdds).count() == 1
    assert "失败" not in note
    row = db.scalar(select(IntlOdds))
    assert abs(row.sp_h - 1.50) < 1e-9  # 赔率已更新


def test_same_source_dedupe_latest_wins(db, monkeypatch):
    """修复2：同 source 多条快照时，市闸只取最新（retrieved 倒序 first-wins）。"""
    mini = _mini_xg(monkeypatch)
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043001", match_no="周三881", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    cn_t = today_cn() + "T12:00:00+08:00"
    db.merge(SPSnapshot(match_id="2043001", pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00, captured_at=cn_t))
    kc = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    utc = lambda h: (kc - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    # 同源两条不同 kickoff_utc（都在 ±4h 匹配窗内）：新快照（retrieved 13:00，贴近竞彩）与旧快照（09:00，离谱）
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=utc(11), sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.flush()
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=utc(10), sp_h=9.99, sp_d=1.01, sp_a=1.01,  # 旧口径离谱
                      retrieved_at=today_cn() + "T09:00:00+00:00"))
    db.commit()
    vs = build_verdicts(db, today_cn(), NOW)
    v = vs[0]
    srcs = v.gates["market"]["detail"]["sources"]
    pin_keys = [k for k in srcs if k.startswith("pinnacle")]
    assert len(pin_keys) == 1  # 同源去重
    assert abs(srcs[pin_keys[0]][0] - 0.6560) < 0.01  # 用的是新快照（1.42 去水≈0.656）


def _mini_xg(monkeypatch, conf=0.45):
    import pandas as pd
    mini = None
    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(24):
        d = base + pd.Timedelta(days=i)
        if i % 2 == 0:
            rows.append(dict(datetime=d, team_home="霸主", team_away="弱旅", xg_home=3.0, xg_away=0.6))
        else:
            rows.append(dict(datetime=d, team_home="弱旅", team_away="霸主", xg_home=0.7, xg_away=2.6))
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    pd.DataFrame(rows).to_csv(path, index=False)
    s2 = Settings(xg_data_path=path, model_conf_threshold=conf,
                  market_div_threshold=0.30, rake_clamp_lo=0.10)
    monkeypatch.setattr(vz, "get_settings", lambda: s2)
    return path


def test_hhad_model_uses_line_adjusted_probs(db, monkeypatch):
    """修复3：让球场的模闸按让球线调整（让球主胜概率 < 裸主胜概率）。"""
    _mini_xg(monkeypatch)
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043002", match_no="周三882", league="德甲",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=False))  # 非单关 → hhad
    db.merge(SPSnapshot(match_id="2043002", pool="hhad", goal_line="-1",
                        sp_h=1.90, sp_d=3.80, sp_a=4.20,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    vs = build_verdicts(db, today_cn(), NOW)
    v = vs[0]
    assert v.pool == "hhad"
    top = v.gates["model"]["detail"]["shrunk"][0]
    # 让一球后主胜概率显著低于裸 1x2（裸 ≈ 0.98）
    assert top < 0.95
    assert v.model_h is not None and v.model_h == top


def test_avoid_includes_any_gate_kill(db, monkeypatch):
    """修复4：市/模砍掉的场也进避雷，why 对应首道死闸。"""
    _mini_xg(monkeypatch, conf=0.95)  # 极高可推线 → 模闸必死
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043003", match_no="周三883", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    db.merge(SPSnapshot(match_id="2043003", pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00,  # 抽水浅 → 价过
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    from app.modules.messaging import build_stream
    s = build_stream(db, today_cn())
    hit = [a for a in s["avoid"] if a["match_no"] == "周三883"]
    assert hit, "模闸砍掉的场必须进避雷"
    assert hit[0]["gate"] == "model" and "模型置信" in hit[0]["why"]


def test_verdict_detail_has_model_and_pick(db, client, monkeypatch):
    _mini_xg(monkeypatch)
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043004", match_no="周三884", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    db.merge(SPSnapshot(match_id="2043004", pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    from urllib.parse import quote
    r = client.get(f"/verdicts/{quote('v' + today_cn() + '-周三884', safe='')}").json()
    assert "model" in r["payload"] and "pick" in r["payload"]["model"]
    assert r["pick"] is not None and r["pick"]["dir"] in ("主胜", "平局", "客胜")


def test_predict_line_math():
    """让球口径单元：强主让 1 球 → 让球主胜概率 < 裸主胜，且三元归一。"""
    import pandas as pd
    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(24):
        d = base + pd.Timedelta(days=i)
        if i % 2 == 0:
            rows.append(dict(datetime=d, team_home="强", team_away="弱", xg_home=3.0, xg_away=0.6))
        else:
            rows.append(dict(datetime=d, team_home="弱", team_away="强", xg_home=0.7, xg_away=2.6))
    m = fit(pd.DataFrame(rows), as_of=pd.Timestamp("2026-11-03 12:00:00").to_pydatetime())
    raw = predict(m, "强", "弱")
    line = predict_line(m, "强", "弱", -1.0)
    assert abs(line.p_home + line.p_draw + line.p_away - 1.0) < 1e-6
    assert line.p_home < raw.p_home       # 让一球更难
    assert line.p_away > raw.p_away       # 让一球后客胜口径概率上升


def test_hhad_market_gate_uses_had_not_hhad(db, monkeypatch):
    """让球判决的市闸必须用 had 对照国际盘 h2h，不能拿 hhad 概率硬比。"""
    _mini_xg(monkeypatch)
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043010", match_no="周三890", league="欧罗巴",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=False))
    db.merge(SPSnapshot(match_id="2043010", pool="had", goal_line="",
                        sp_h=1.80, sp_d=3.50, sp_a=4.20,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.merge(SPSnapshot(match_id="2043010", pool="hhad", goal_line="-1",
                        sp_h=2.90, sp_d=3.40, sp_a=2.20,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    cn = timezone(timedelta(hours=8))
    utc = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=cn).astimezone(timezone.utc).isoformat()
    db.merge(IntlOdds(source="pinnacle", sport="soccer_uefa_europa_league",
                      league="Europa League", home_raw="Dominator",
                      away_raw="Weak", home="霸主", away="弱旅",
                      kickoff_utc=utc, sp_h=1.82, sp_d=3.45, sp_a=4.10,
                      retrieved_at=datetime.now(timezone.utc).isoformat()))
    db.commit()

    v = build_verdicts(db, today_cn(), NOW)[0]
    assert v.pool == "hhad"
    mg = v.gates["market"]
    assert mg["detail"]["market_pool"] == "had"
    assert mg["detail"]["verdict_pool"] == "hhad"
    assert mg["detail"]["divergence"] < 0.05


def test_market_gate_uses_sportmonks_pinnacle_without_odds_api(db, monkeypatch):
    """Sportmonks Pinnacle 1X2 可作为竞彩官方之外的第二市场源，不依赖 Odds API。"""
    _mini_xg(monkeypatch)
    kick = future_kickoff(today_cn())
    mid = "2043011"
    db.merge(SPMatch(match_id=mid, match_no="周三891", league="欧罗巴",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=1.80, sp_d=3.50, sp_a=4.20,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.merge(SportmonksMatchData(
        match_id=mid, fixture_id=880011, league="欧罗巴",
        home_name="霸主", away_name="弱旅", kickoff_utc=kick,
        odds={"home": 0.53, "draw": 0.26, "away": 0.21},
        bookmaker="Pinnacle", source="manual",
        data_cutoff="2026-11-11T12:00:00"))
    db.commit()

    v = build_verdicts(db, today_cn(), NOW)[0]
    mg = v.gates["market"]
    assert mg["result"] == "pass", mg
    assert "Sportmonks(Pinnacle)" in mg["detail"]["sources"]
    assert mg["detail"]["divergence"] < 0.05
    assert v.model_status in ("shadow", "unavailable")
    assert v.tier in ("verified", "market_reference")
    assert v.data_quality["market"] == "pass"


def test_intl_sync_only_requests_matched_events(db, monkeypatch):
    from app.modules.intl_odds import sync_the_odds_api
    from tests.conftest import future_kickoff, today_cn
    from datetime import datetime, timezone
    from app.modules.intl_odds import CN

    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043888", match_no="周四888", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    db.commit()
    kick_utc = (datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
                .replace(tzinfo=CN).astimezone(timezone.utc)
                .isoformat().replace("+00:00", "Z"))
    listed = [
        {"id": "ev-match", "home_team": "霸主", "away_team": "弱旅",
         "commence_time": kick_utc},
        {"id": "ev-other", "home_team": "Other", "away_team": "Team",
         "commence_time": kick_utc},
    ]
    seen = {}

    def fetch_list(sport):
        return listed

    def fetch_odds(sport, ids):
        seen["ids"] = ids
        return [{
            "id": "ev-match", "sport_title": "EPL", "commence_time": kick_utc,
            "home_team": "霸主", "away_team": "弱旅",
            "bookmakers": [{"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [
                {"name": "霸主", "price": 1.8},
                {"name": "Draw", "price": 3.5},
                {"name": "弱旅", "price": 4.2},
            ]}]}],
        }]

    n, _ = sync_the_odds_api(
        db, Aligner(db), datetime.now(timezone.utc), api_key="test",
        fetch_events=fetch_odds, fetch_event_list=fetch_list,
        sports=["soccer_epl"])
    assert n == 1
    assert seen["ids"] == ["ev-match"]
    assert db.query(IntlOdds).count() == 1


def test_intl_sync_skips_odds_when_no_target_event(db, monkeypatch):
    from app.modules.intl_odds import sync_the_odds_api
    from tests.conftest import future_kickoff, today_cn
    from datetime import datetime, timezone

    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2043889", match_no="周四889", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    db.commit()

    called = {"odds": 0}

    def fetch_odds(sport, ids):
        called["odds"] += 1
        return []

    n, note = sync_the_odds_api(
        db, Aligner(db), datetime.now(timezone.utc), api_key="test",
        fetch_events=fetch_odds,
        fetch_event_list=lambda sport: [
            {"id": "x", "home_team": "Other", "away_team": "Team",
             "commence_time": "2026-11-06T00:00:00Z"}],
        sports=["soccer_epl"])
    assert n == 0
    assert called["odds"] == 0
    assert "不请求" in note or "0 场" in note
