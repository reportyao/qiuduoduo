"""W3 三道闸引擎测试。

关键保真度断言：DC 移植版在 2023-24 英超留一日回测的 log loss 应与 W1 结果
（0.9191）同水位 —— 断言 < 0.95，漂移即失败。
"""
import math

import pandas as pd
import pytest
from datetime import datetime, timedelta

from app.config import Settings
from app.models import IntlOdds, SPMatch, SPSnapshot, Verdict
from app.modules import verdict as vz
from app.modules.dc_model import backtest_logloss, fit, predict
from app.modules.gates import (best_pick, breakeven_prob, divergence,
                               dynamic_threshold, implied_probs, market_gate,
                               model_gate, price_gate, shrink_to_market)
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


# ---------- 价闸：动态阈值 ----------

def test_dynamic_threshold_median_plus_pad():
    rakes = [0.08] * 4 + [0.09, 0.10, 0.11, 0.12, 0.13]  # median = 0.09
    t = dynamic_threshold(rakes, pad=0.03, lo=0.10, hi=0.13)
    assert abs(t - 0.12) < 1e-9  # 0.09 + 0.03
    t2 = dynamic_threshold([0.06] * 10, pad=0.03, lo=0.10, hi=0.13)
    assert abs(t2 - 0.10) < 1e-9  # 0.09 → clamp lo
    assert dynamic_threshold([0.1] * 3, 0.03, 0.10, 0.13) == 0.10  # 候选<5 保守取 lo


def test_price_gate_dynamic():
    assert price_gate(0.092, 0.113).result == "pass"
    assert price_gate(0.134, 0.113).result == "fail"


# ---------- 市闸：离散度 ----------

def test_divergence_and_market_gate():
    a = (0.55, 0.25, 0.20)
    b = (0.50, 0.28, 0.22)
    assert abs(divergence({"竞彩": a, "pinnacle": b}) - 0.05) < 1e-9
    g = market_gate({"竞彩": a, "pinnacle": b}, threshold=0.05)
    assert g.result == "fail"  # 恰在边界（< 严格）
    g2 = market_gate({"竞彩": a, "pinnacle": (0.53, 0.26, 0.21)}, threshold=0.05)
    assert g2.result == "pass"
    # 单源 → pending_data（诚实）
    g3 = market_gate({"竞彩": a}, 0.05)
    assert g3.result == "pending_data"


# ---------- 模闸：收缩 + 可推线 ----------

def test_shrink_discipline_matches_w1():
    # 偏差 >8pp 的方向被砍半并归一
    m = (0.70, 0.20, 0.10)
    k = (0.50, 0.30, 0.20)
    s = shrink_to_market(m, k)
    assert abs(sum(s) - 1.0) < 1e-9
    assert s[0] < m[0] and s[0] > k[0]  # 被拉向市场
    # 偏差 ≤8pp 不收缩
    s2 = shrink_to_market((0.52, 0.28, 0.20), (0.50, 0.30, 0.20))
    assert abs(s2[0] - 0.52) < 1e-9


def test_best_pick_ev():
    pk = best_pick((0.55, 0.25, 0.20), (2.05, 3.4, 4.2))
    assert pk["dir"] == "主胜"
    assert abs(pk["ev"] - (0.55 * 2.05 - 1)) < 1e-9


def test_model_gate_thresholds():
    g1 = model_gate((0.60, 0.25, 0.15), (2.0, 3.4, 4.0), 0.53)
    assert g1.result == "pass" and g1.detail["pick"]["dir"] == "主胜"
    g2 = model_gate((0.45, 0.30, 0.25), (2.0, 3.4, 4.0), 0.53)
    assert g2.result == "fail"
    g3 = model_gate(None, (2.0, 3.4, 4.0), 0.53)
    assert g3.result == "pending_data"


# ---------- DC 模型：预测合法性 + 保真度 ----------

def _synthetic_xg(n=24):
    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(n):
        d = base + pd.Timedelta(days=i)
        if i % 2 == 0:
            rows.append(dict(datetime=d, team_home="霸主", team_away="弱旅",
                             xg_home=3.0, xg_away=0.6))
        else:
            rows.append(dict(datetime=d, team_home="弱旅", team_away="霸主",
                             xg_home=0.7, xg_away=2.6))
    return pd.DataFrame(rows)


def test_dc_predict_sanity():
    m = fit(_synthetic_xg(), as_of=pd.Timestamp("2026-11-03 12:00:00").to_pydatetime())
    p = predict(m, "霸主", "弱旅")
    assert p is not None
    assert abs(p.p_home + p.p_draw + p.p_away - 1.0) < 1e-6
    assert p.lambda_home > p.lambda_away  # 强主队
    assert predict(m, "霸主", "不存在队") is None


def test_dc_backtest_logloss_close_to_w1():
    """移植保真度：2023-24 英超真实 xG 留一日回测，log loss < 0.95（W1 v1 = 0.9191）。"""
    df = pd.read_csv("../w1-validation/xg_matches.csv")
    epl = df[(df["competition"] == "ENG Premier League") &
             (df["datetime"] >= "2024-01-01") & (df["datetime"] < "2024-07-01")].copy()
    ll = backtest_logloss(epl, halflife_days=180, window_days=540, rho=-0.06, min_matches=3)
    assert ll < 0.95, f"DC 移植漂移：log loss {ll:.4f} 应接近 W1 的 0.9191"


# ---------- 端到端：三关全过 → promoted ----------

def test_full_promotion_pipeline(db, client, monkeypatch, tmp_path):
    mini = tmp_path / "xg_mini.csv"
    _synthetic_xg().to_csv(mini, index=False)
    s2 = Settings(xg_data_path=str(mini), model_conf_threshold=0.45,
                  market_div_threshold=0.30, rake_clamp_lo=0.10)
    monkeypatch.setattr(vz, "get_settings", lambda: s2)

    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2042801", match_no="周三777", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=True))
    cn_t = today_cn() + "T12:00:00+08:00"
    db.merge(SPSnapshot(match_id="2042801", pool="had", goal_line="",
                        sp_h=1.40, sp_d=4.60, sp_a=7.00, captured_at=cn_t))
    # 国际盘（pinnacle，与竞彩接近 → 离散小 → 市闸过）；kickoff 落在 ±4h 匹配窗内（赛前 3h）
    kc = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    intl_utc = (kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOMINATOR", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=intl_utc,
                      sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T12:00:00+00:00"))
    db.commit()

    vs = build_verdicts(db, today_cn(), NOW)
    assert len(vs) == 1
    v = vs[0]
    assert v.gates["price"]["result"] == "pass"
    assert v.gates["market"]["result"] == "pass"
    assert v.gates["model"]["result"] == "pass"
    assert v.status == "promoted"
    assert v.pick is not None and v.pick["dir"] in ("主胜", "平局", "客胜")
    # payload 证据链：每条含 tag+src（F3 gate：每条可溯源）
    ev = v.payload["evidence"]
    assert len(ev) >= 4 and all(e["tag"] and e["src"] for e in ev)
    assert any("the-odds-api" in e["src"] for e in ev)
    assert any("DC v1.1" in e["t"] for e in ev)

    # /stream 出 promoted；why-not 报 promoted
    body = client.get("/stream").json()
    assert body["stats"]["promoted"] == 1 and len(body["verdicts"]) == 1
    r = client.get(f"/matches/2042801/why-not").json()
    assert r["status"] == "promoted"
    # evidence 端点
    vid = quote_id(v.id)
    ev2 = client.get(f"/verdicts/{vid}/evidence").json()
    assert ev2["evidence"] == ev
    # sale-schedule（F10）
    ss = client.get("/matches/sale-schedule").json()
    assert ss["items"] and ss["items"][0]["sale_close"] == ss["items"][0]["kickoff"]


def quote_id(vid: str) -> str:
    from urllib.parse import quote
    return quote(vid, safe="")


def test_why_not_dead_reason_matches_gates(db, client):
    """F6 gate：死因与闸门日志 100% 一致。"""
    db.merge(SPMatch(match_id="2042802", match_no="周三778", league="英超",
                     home_raw="利物浦", away_raw="埃弗顿", home="利物浦", away="埃弗顿",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2042802", pool="had", goal_line="",
                        sp_h=1.20, sp_d=4.50, sp_a=9.00,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    r = client.get("/matches/2042802/why-not").json()
    assert r["dead_gate"] == "price"  # 深水场唯一死因
    assert "抽水" in r["title"]
    # 审计可对拍：model_runs 里 price fail 存在且 detail 一致
    runs = r["audit"]["model_runs"]
    assert any(x["gate"] == "price" and x["result"] == "fail" for x in runs)
    assert r["audit"]["verdict_hash"]
    assert r["whatif"]


def test_market_gate_pending_without_intl(db, client):
    db.merge(SPMatch(match_id="2042803", match_no="周三779", league="英超",
                     home_raw="小球队", away_raw="另一队", home="小球队", away="另一队",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2042803", pool="had", goal_line="",
                        sp_h=2.10, sp_d=3.30, sp_a=3.60,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    vs = build_verdicts(db, today_cn(), NOW)
    assert vs[0].status == "screening"  # 价过 · 市单源 pending · 模 pending
    assert vs[0].gates["market"]["result"] == "pending_data"
