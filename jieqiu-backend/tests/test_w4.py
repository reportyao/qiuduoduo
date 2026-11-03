"""W4 测试：哈希链+锚点、结算、SSE 降级、校准回测、公开账本。"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import DailyAnchor, MatchResult, SPMatch, SPSnapshot, Verdict, VerdictRevision
from app.modules import verdict as vz
from app.modules.align import Aligner
from app.modules.sealchain import build_anchor, link_revision, verify_day
from app.modules.settle import _outcome_handicap, settle_verdicts, sync_results_football_data
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


def _mini(monkeypatch, conf=0.45):
    import os
    import tempfile
    import pandas as pd
    from app.config import Settings
    rows = []
    base = pd.Timestamp("2026-09-01 20:00:00")
    for i in range(24):
        d = base + pd.Timedelta(days=i)
        if i % 2 == 0:
            rows.append(dict(datetime=d, team_home="霸主", team_away="弱旅", xg_home=3.0, xg_away=0.6))
        else:
            rows.append(dict(datetime=d, team_home="弱旅", team_away="霸主", xg_home=0.7, xg_away=2.6))
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    pd.DataFrame(rows).to_csv(path, index=False)
    s2 = Settings(xg_data_path=path, model_conf_threshold=conf,
                  market_div_threshold=0.30, rake_clamp_lo=0.10)
    monkeypatch.setattr(vz, "get_settings", lambda: s2)
    return path


def _seed_match(db, mid, no, home, away, sp=(1.40, 4.60, 7.00), single=True):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw=home, away_raw=away, home=home, away=away,
                     kickoff=future_kickoff(today_cn()), single_flag=single))
    db.merge(SPSnapshot(match_id=mid, pool="had" if single else "hhad",
                        goal_line="" if single else "-1",
                        sp_h=sp[0], sp_d=sp[1], sp_a=sp[2],
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()


# ---------- 哈希链 + 锚点 ----------

def test_chain_links_and_verify(db, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044001", "周四001", "霸主", "弱旅")
    vs = build_verdicts(db, today_cn(), NOW)
    assert len(vs) == 1
    # 第二次构建：赔率变化 → 新修订 → 链两节相链
    db.merge(SPSnapshot(match_id="2044001", pool="had", goal_line="",
                        sp_h=1.45, sp_d=4.50, sp_a=6.90,
                        captured_at=today_cn() + "T13:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    revs = db.scalars(select(VerdictRevision).order_by(VerdictRevision.id)).all()
    assert len(revs) == 2
    assert revs[1].chain_prev == revs[0].chain_hash  # 链相扣
    build_anchor(db, today_cn())
    rep = verify_day(db, today_cn())
    assert rep["ok"] and rep["links"] == 2 and rep["anchor_match"]


def test_chain_tamper_detected(db, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044002", "周四002", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    assert verify_day(db, today_cn())["ok"]
    # 篡改：改一条修订的 payload_hash（模拟改历史）
    rev = db.scalars(select(VerdictRevision)).first()
    rev.payload_hash = "f" * 64
    db.commit()
    rep = verify_day(db, today_cn())
    assert not rep["ok"] and rep["broken_at"] is not None


def test_anchor_chains_across_days(db, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044003", "周三003", "霸主", "弱旅")
    build_verdicts(db, "2026-11-02", "2026-11-02 19:00:00")
    build_anchor(db, "2026-11-02")
    a1 = db.get(DailyAnchor, "2026-11-02")
    _seed_match(db, "2044004", "周四004", "霸主", "弱旅")
    build_verdicts(db, "2026-11-03", NOW)
    build_anchor(db, "2026-11-03")
    a2 = db.get(DailyAnchor, "2026-11-03")
    assert a2.prev_root == a1.root_hash  # 跨日相链
    assert verify_day(db, "2026-11-03")["ok"]

    # 已出现 11-03 锚点后，迟到的 11-02 修订绝不能重写旧锚，否则 11-03 永久断链。
    late = VerdictRevision(verdict_id="v2026-11-02-周三003", trade_date="2026-11-02",
                           payload={"trade_date": "2026-11-02"}, payload_hash="late" * 16)
    db.add(late)
    db.flush()
    link_revision(db, late)
    db.commit()
    old_root = a1.root_hash
    build_anchor(db, "2026-11-02")
    assert db.get(DailyAnchor, "2026-11-02").root_hash == old_root
    assert verify_day(db, "2026-11-03")["ok"]


# ---------- 结算 ----------

def test_settlement_1x2_and_handicap(db, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044005", "周四005", "霸主", "弱旅")  # pick → 主胜
    build_verdicts(db, today_cn(), NOW)
    kick = future_kickoff(today_cn())
    ko = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    euro_date = (ko - timedelta(days=1)).strftime("%Y-%m-%d")  # 欧洲晚场 → 北京次日凌晨
    db.merge(MatchResult(source="football-data", league="英超",
                         home_raw="Dominator", away_raw="Weak", home="霸主", away="弱旅",
                         match_date=euro_date, goals_home=2, goals_away=0,
                         retrieved_at=today_cn() + "T23:00:00+08:00"))
    db.commit()
    n = settle_verdicts(db, today_cn())
    assert n == 1
    v = db.scalars(select(Verdict)).first()
    assert v.settled == "win" and v.result_score == "2-0"


def test_handicap_settlement_math():
    """让球结算单元：主-1 时 2-0 → 让球主胜；1-0 → 让平；2-1 → 让球主胜；0-1 → 让客胜。"""
    assert _outcome_handicap(2, 0, -1.0) == "主胜"
    assert _outcome_handicap(1, 0, -1.0) == "平局"
    assert _outcome_handicap(2, 1, -1.0) == "平局"  # 2-1 让一球 → 净胜 0
    assert _outcome_handicap(3, 1, -1.0) == "主胜"
    assert _outcome_handicap(0, 1, -1.0) == "客胜"


def test_results_sync_from_football_data(db):
    """赛果同步（注入本地 CSV 文本，不起网络）。"""
    from app.modules.align import Aligner, seed_aliases
    seed_aliases(db)
    csv_text = ("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\r\n"
                "E0,01/11/2026,15:00,Arsenal,Burnley,3,1\r\n"
                "E0,01/11/2026,17:30,Man City,Bournemouth,2,2\r\n")
    def fake_fetch(code, season):
        return csv_text if code == "E0" else ""
    n, note = sync_results_football_data(db, Aligner(db), fetch=fake_fetch)
    assert n == 2
    from app.models import MatchResult as MR
    rows = db.scalars(select(MR)).all()
    pairs = {(r.home, r.away) for r in rows}
    assert ("阿森纳", "伯恩利") in pairs and ("曼城", "伯恩茅斯") in pairs
    # 幂等
    n2, _ = sync_results_football_data(db, Aligner(db), fetch=fake_fetch)
    assert n2 == 0


# ---------- 叙述流（降级兜底 gate） ----------

def test_narration_stream_fallback_and_personas(db, client, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044006", "周四006", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    v = db.scalars(select(Verdict)).first()
    vid = v.id
    texts = {}
    for persona in ("zhuanjia", "laopao", "meng"):
        r = client.get(f"/verdicts/{vid}/narration.stream", params={"persona": persona})
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = r.text
        assert "event: done" in body
        texts[persona] = body
        assert "404" not in body[:20]  # 不出错
    assert texts["zhuanjia"] != texts["laopao"] != texts["meng"]
    # 弱网降级 gate：哪怕 provider 抛异常（内部 llm_available 恒 False → 模板），仍有完整 done
    assert "template_id" in texts["zhuanjia"]


# ---------- 校准回测 ----------

def test_backtest_calibration_metrics(db, client):
    from app.modules.backtest import evaluate
    import pandas as pd
    df = pd.read_csv("../w1-validation/xg_matches.csv")  # 全量历史（衰减窗口自行截取）
    epl = df[df["competition"] == "ENG Premier League"]  # 评估窗口在参数里，历史必须给足
    m = evaluate(epl, "2024-01-01", "2024-06-30",
                 halflife_days=180, window_days=540, rho=-0.06, min_matches=3)
    assert m["n"] > 50 and m["logloss"] < 0.95
    assert 0 < m["accuracy"] < 1
    assert len(m["calibration"]) >= 3
    for c in m["calibration"]:
        assert 0 <= c["mean_predicted"] <= 1 and 0 <= c["observed_freq"] <= 1
    # 入库 + 端点
    from app.models import ModelEval
    db.add(ModelEval(label="test", params=m["params"], metrics=m))
    db.commit()
    r = client.get("/model/evals").json()
    assert any(e["label"] == "test" for e in r)


# ---------- 公开账本 ----------

def test_ledger_page_and_api(db, client, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2044007", "周四007", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    r = client.get("/ledger")
    assert r.status_code == 200 and "公开账本" in r.text and "当前连败" in r.text
    api = client.get("/api/ledger").json()
    assert api["stats"]["promoted_total"] >= 0
    assert all(it["hash"] for it in api["items"])
    # 锚点端点
    a = client.get(f"/anchor/{today_cn()}").json()
    assert a["root_hash"] and a["verify"].startswith("/chain/verify")


def test_health_chain_field_and_alert(db, client, monkeypatch):
    """遗漏A：/health 暴露链健康（断链告警可观测入口）。"""
    _mini(monkeypatch)
    _seed_match(db, "2044008", "周四008", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    h = client.get("/health").json()
    assert h["chain"]["ok"] is True and h["chain"]["links"] >= 1
    # 篡改 → health 里的链状态翻红（断链告警演练）
    rev = db.scalars(select(VerdictRevision)).first()
    rev.payload_hash = "e" * 64
    db.commit()
    h2 = client.get("/health").json()
    assert h2["chain"]["ok"] is False and h2["chain"]["broken_at"] is not None


def test_seal_exposes_chain(db, client, monkeypatch):
    """遗漏B：seal 附链位，外部可对单条判决验链。"""
    _mini(monkeypatch)
    _seed_match(db, "2044009", "周四009", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    from urllib.parse import quote
    v = db.scalars(select(Verdict)).first()
    s = client.get(f"/verdicts/{quote(v.id, safe='')}/seal").json()
    assert s["chain"]["hash"] and len(s["chain"]["hash"]) == 64
    assert "chain_hash" in s["revisions"][0]


def test_anchor_external_offline_verification(db, client, monkeypatch):
    """遗漏C（F14 gate：外部独立核验）：用 anchor 响应自带的 chain_hashes 离线重算 root。"""
    import hashlib
    _mini(monkeypatch)
    _seed_match(db, "2044010", "周四010", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    a = client.get(f"/anchor/{today_cn()}").json()
    recomputed = hashlib.sha256(
        f"{a['prev_root']}|{a['date']}|{a['revision_count']}|{'|'.join(a['chain_hashes'])}".encode()
    ).hexdigest()
    assert recomputed == a["root_hash"]  # 完全离线复算成立


def test_chain_verify_default_latest_anchor(db, client, monkeypatch):
    """遗漏D：verify 缺省日期 = 最新锚点日。"""
    _mini(monkeypatch)
    _seed_match(db, "2044011", "周四011", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    build_anchor(db, today_cn())
    r = client.get("/chain/verify").json()
    assert r["date"] == today_cn() and r["ok"]


def test_rebuild_day_chain_repairs_unlinked(db, monkeypatch):
    """review：rebuild_day_chain 修复路径（如历史数据无链字段时补链）。"""
    from app.modules.sealchain import rebuild_day_chain
    _mini(monkeypatch)
    _seed_match(db, "2044012", "周四012", "霸主", "弱旅")
    build_verdicts(db, today_cn(), NOW)
    # 模拟历史脏数据：清空链字段
    for r in db.scalars(select(VerdictRevision)).all():
        r.chain_prev = ""
        r.chain_hash = ""
    db.commit()
    n = rebuild_day_chain(db, today_cn())
    assert n >= 1
    build_anchor(db, today_cn())
    assert verify_day(db, today_cn())["ok"]


def test_ledger_escapes_html(db, client, monkeypatch):
    """review：账本 HTML 对队名转义（XSS 卫生）。"""
    _mini(monkeypatch)
    evil = "<script>alert(1)</script>"
    db.merge(SPMatch(match_id="2044013", match_no="周四013", league="英超",
                     home_raw=evil, away_raw="弱旅", home=evil, away="弱旅",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2044013", pool="had", goal_line="",
                        sp_h=2.0, sp_d=3.4, sp_a=3.8,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    page = client.get("/ledger").text
    assert "<script>alert" not in page  # 已转义
    assert "&lt;script&gt;" in page


def test_hhad_settlement_e2e(db, monkeypatch):
    """review：让球判决端到端结算（pick 让球主胜 + 2-0 → win）。"""
    _mini(monkeypatch)
    kick = future_kickoff(today_cn())
    db.merge(SPMatch(match_id="2044014", match_no="周四014", league="英超",
                     home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                     kickoff=kick, single_flag=False))
    db.merge(SPSnapshot(match_id="2044014", pool="hhad", goal_line="-1",
                        sp_h=1.90, sp_d=3.80, sp_a=4.20,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    ko = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    euro_date = (ko - timedelta(days=1)).strftime("%Y-%m-%d")
    db.merge(MatchResult(source="football-data", league="英超",
                         home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                         match_date=euro_date, goals_home=2, goals_away=0,
                         retrieved_at=today_cn() + "T23:00:00+08:00"))
    db.commit()
    assert settle_verdicts(db, today_cn()) == 1
    v = db.scalars(select(Verdict)).first()
    assert v.settled == "win" and v.result_score == "2-0"
    assert v.pick["dir"] == "主胜"  # 让球主胜口径
