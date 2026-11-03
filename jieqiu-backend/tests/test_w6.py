"""W6 测试：F11 回放 100% · F12 归因确定性 · F13 冲突必问 · F15 意图≥85% · F7 非比赛日。"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Bet, IntlOdds, MatchResult, Memory, SPMatch, SPSnapshot, User, Verdict
from app.modules import verdict as vz
from app.modules.chat import route_intent
from app.modules.messaging import build_stream
from app.modules.postmortem import attribute, killed_outcomes, postmortem
from app.modules.users import (clear_rest, login_device, replay_streak, set_rest,
                               upsert_memory, user_streak)
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


def _seed_match(db, mid, no, home="霸主", away="弱旅", sp=(1.40, 4.60, 7.00)):
    db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                     home_raw=home, away_raw=away, home=home, away=away,
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                        sp_h=sp[0], sp_d=sp[1], sp_a=sp[2],
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()


def _add_intl(db, home="霸主", away="弱旅"):
    """市闸第二源：让该对阵可晋升（kickoff 落在 ±4h 匹配窗）。"""
    kick = future_kickoff(today_cn())
    kc = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home=home, away=away,
                      kickoff_utc=(kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                      sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.commit()


# ---------- F11：连败保护（回放 gate：100%） ----------

def test_replay_streak_100_percent():
    """回放 gate：构造 8 种序列，触发判定必须全对。"""
    cases = [
        (["win"], 0, False),
        (["lose"], 1, False),
        (["lose", "lose"], 2, False),
        (["lose", "lose", "lose"], 3, True),
        (["win", "lose", "lose", "lose"], 3, True),
        (["lose", "lose", "lose", "win"], 0, False),        # win 清零
        (["lose", "win", "lose", "lose", "lose"], 3, True),
        (["lose", "lose", "win", "lose", "lose"], 2, False),
    ]
    for results, exp_streak, exp_trigger in cases:
        r = replay_streak(results, threshold=3)
        assert r["streak"] == exp_streak and r["triggered"] == exp_trigger, f"回放失败: {results}"


def test_user_streak_e2e_and_protection_in_stream(db, client, monkeypatch):
    _mini(monkeypatch)
    # 3 场已结算败局（用历史日期）+ 1 场今晚可推
    import json
    import urllib.request
    from urllib.parse import quote
    user, _ = login_device(db, "tok-streak")
    # 今晚这场用未来 kickoff（进构建窗口）
    for i, (mid, no, ko) in enumerate([
            ("2045001", "周一001", "2026-11-01 21:00:00"),
            ("2045002", "周二001", "2026-11-02 21:00:00"),
            ("2045003", "周三001", future_kickoff(today_cn(), 22, 30))]):
        db.merge(SPMatch(match_id=mid, match_no=no, league="英超",
                         home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                         kickoff=ko, single_flag=True))
        db.merge(SPSnapshot(match_id=mid, pool="had", goal_line="",
                            sp_h=1.40, sp_d=4.60, sp_a=7.00,
                            captured_at="2026-11-01T10:00:00+08:00"))
    # 赛果只放一条（unique: home+away+date）
    db.merge(MatchResult(source="football-data", league="英超",
                         home_raw="霸主", away_raw="弱旅", home="霸主", away="弱旅",
                         match_date="2026-11-01", goals_home=0, goals_away=1,
                         retrieved_at="2026-11-02T10:00:00+08:00"))
    # 国际盘（2045003 市闸过 → 可晋升）
    ko3 = datetime.strptime("2026-11-03 22:30:00", "%Y-%m-%d %H:%M:%S")
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=(ko3 - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                      sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.commit()
    # 三个不同日期的判决需要各自赛果 —— 简化：build 只针对 today，前两场手动造已结算败局判决
    vs = build_verdicts(db, today_cn(), NOW)  # 今晚这场 → promoted
    assert vs and vs[0].status == "promoted"
    for mid, no in [("2045001", "周一001"), ("2045002", "周二001")]:
        db.merge(SPMatch) if False else None
    # 手动造两注历史败局（直接写 Verdict 行，绕过日期窗口）
    for i, (mid, no, ko) in enumerate([
            ("2045001", "周一001", "2026-11-01 21:00:00"),
            ("2045002", "周二001", "2026-11-02 21:00:00")]):
        v = Verdict(id=f"v2026-11-0{i+1}-{no}", trade_date=f"2026-11-0{i+1}",
                    match_id=mid, match_no=no, league="英超", home="霸主", away="弱旅",
                    kickoff=ko, pool="had", goal_line="", sp_h=1.4, sp_d=4.6, sp_a=7.0,
                    rake=0.069, p_home=0.62, p_draw=0.21, p_away=0.17,
                    status="promoted", gates={}, payload={"id": f"v{i}", "trade_date": f"2026-11-0{i+1}"},
                    payload_hash="a" * 64, pick={"dir": "主胜", "prob": 0.66, "sp": 1.4, "ev": -0.07},
                    settled="lose", result_score="0-1")
        db.merge(v)
        db.commit()
    # 用户 3 注全败（两历史 + 今晚一场赛果后……今晚未结算，先只算 2 败 → 未触发；再下今晚注后 mock 不结算）
    db.add(Bet(user_id=user.id, verdict_id="v2026-11-01-周一001", amount=100, pick_dir="主胜"))
    db.add(Bet(user_id=user.id, verdict_id="v2026-11-02-周二001", amount=100, pick_dir="主胜"))
    db.commit()
    st = user_streak(db, user)
    assert st["streak"] == 2 and not st["active"]
    # 第三败（今晚判决在测试中手动结算为 lose）
    db.add(Bet(user_id=user.id, verdict_id=vs[0].id, amount=100, pick_dir="主胜"))
    db.commit()
    tv = db.get(Verdict, vs[0].id)
    tv.settled = "lose"
    tv.result_score = "0-2"
    db.commit()
    st = user_streak(db, user)
    assert st["streak"] == 3 and st["active"]  # 触发
    # 流里出现保护块
    body = client.get("/stream", headers={"Authorization": "Bearer tok-streak"}).json()
    assert body.get("you", {}).get("protection_active") is True
    # 关闭保护 → active 翻 False
    r = client.post("/me/discipline", json={"enabled": False},
                    headers={"Authorization": "Bearer tok-streak"}).json()
    assert r["discipline_on"] is False and r["streak"]["active"] is False


# ---------- F12：归因（确定性 → 正确率 100% ≥ 90%） ----------

def _mk_verdict(settled, pick_prob, market_pending=False, raw_dev=None):
    v = Verdict(id=f"pm-{settled}-{pick_prob}", trade_date="2026-11-03",
                match_id="x", match_no="x", league="英超", home="A", away="B",
                kickoff="2026-11-03 21:00:00", pool="had", goal_line="",
                sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.55, p_draw=0.25,
                p_away=0.20, status="promoted", gates={},
                payload={"id": "pm", "trade_date": "2026-11-03",
                         "model": {"raw": ([0.55 + raw_dev, 0.25, 0.20 - raw_dev]
                                           if raw_dev else None)}},
                payload_hash="b" * 64,
                pick={"dir": "主胜", "prob": pick_prob, "sp": 1.5, "ev": -0.05},
                settled=settled, result_score="0-1")
    if market_pending:
        v.gates = {"market": {"result": "pending_data", "detail": {}}}
    return v


def test_attribution_classes_deterministic():
    """F12 gate：归因抽检正确率 ≥90% —— 规则确定性，构造用例全对。"""
    cases = [
        (_mk_verdict("lose", 0.66, market_pending=True), "信息不足"),
        (_mk_verdict("lose", 0.66, raw_dev=0.12), "强判断落空"),
        (_mk_verdict("lose", 0.62), "高置信落空"),
        (_mk_verdict("lose", 0.54), "随机波动"),
        (_mk_verdict("win", 0.62), "判断兑现"),
        (_mk_verdict(None, 0.62), None),
    ]
    correct = sum(1 for v, exp in cases if attribute(v)["class"] == exp)
    assert correct / len(cases) >= 0.9
    assert correct == len(cases)  # 确定性规则应全对


def test_postmortem_endpoint(db, client, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2045010", "周四010")
    # 国际盘（市闸过 → promoted）
    kick = future_kickoff(today_cn())
    kc = datetime.strptime(kick, "%Y-%m-%d %H:%M:%S")
    db.merge(IntlOdds(source="pinnacle", sport="soccer_epl", league="EPL",
                      home_raw="DOM", away_raw="WEAK", home="霸主", away="弱旅",
                      kickoff_utc=(kc - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                      sp_h=1.42, sp_d=4.50, sp_a=6.80,
                      retrieved_at=today_cn() + "T13:00:00+00:00"))
    db.commit()
    build_verdicts(db, today_cn(), NOW)
    v = db.scalars(select(Verdict)).first()
    r = client.get(f"/verdicts/{v.id}/postmortem").json()
    assert r["kind"] == "promoted" and "whatif" in r
    # 未结算 → 不归因
    assert r["attribution"]["settled"] is False


def test_killed_outcomes_honest_disclosure(db, monkeypatch):
    """what-if：砍对/砍错对称披露。"""
    _mini(monkeypatch)
    for i, settled in enumerate(("lose", "lose", "win", None)):
        v = Verdict(id=f"kill{i}", trade_date="2026-11-03", match_id=f"k{i}",
                    match_no=f"周三00{i}", league="英超", home="A", away="B",
                    kickoff="2026-11-03 21:00:00", pool="had", goal_line="",
                    sp_h=1.2, sp_d=4.5, sp_a=9.0, rake=0.143, p_home=0.71,
                    p_draw=0.19, p_away=0.10, status="killed",
                    gates={"price": {"result": "fail", "detail": {}}},
                    payload={"id": f"kill{i}", "trade_date": "2026-11-03"},
                    payload_hash="c" * 64,
                    settled=settled, result_score="0-1" if settled else None)
        db.merge(v)
    db.commit()
    ko = killed_outcomes(db)
    assert ko["would_lose"] == 2 and ko["would_win"] == 1
    assert ko["avoided_loss_cny"] == 200 and ko["missed_win_cny"] == 100


# ---------- F13：记忆（冲突必问不静默覆盖） ----------

def test_memory_conflict_must_ask(db):
    user, _ = login_device(db, "tok-mem")
    m, st = upsert_memory(db, user.id, "主队偏好", "曼城")
    assert st == "created"
    # 冲突：不同值 + 未 confirm → 拒绝
    m2, st2 = upsert_memory(db, user.id, "主队偏好", "利物浦")
    assert st2 == "conflict" and m2 is None
    # 旧值未被动过（绝不静默覆盖）
    ms = {x.key: x.value for x in db.scalars(select(Memory)).all()}
    assert ms["主队偏好"] == "曼城"
    # confirm → 覆盖
    m3, st3 = upsert_memory(db, user.id, "主队偏好", "利物浦", confirm=True)
    assert st3 == "updated" and m3.value == "利物浦"
    # 相同值 → updated（非冲突）
    m4, st4 = upsert_memory(db, user.id, "主队偏好", "利物浦")
    assert st4 == "updated"


def test_memory_endpoints_auth_and_conflict_409(db, client):
    r = client.post("/auth/device", json={"device_token": "tok-mem2", "display_name": "测试"})
    assert r.status_code == 200 and r.json()["created"] is True
    tok = {"Authorization": "Bearer tok-mem2"}
    assert client.put("/me/memories/主队偏好", json={"value": "曼城"},
                      headers=tok).json()["status"] == "created"
    r2 = client.put("/me/memories/主队偏好", json={"value": "利物浦"}, headers=tok)
    assert r2.status_code == 409
    assert "confirm" in r2.json()["detail"]["message"]
    r3 = client.put("/me/memories/主队偏好", json={"value": "利物浦", "confirm": True},
                    headers=tok)
    assert r3.json()["status"] == "updated"
    assert client.delete("/me/memories/主队偏好", headers=tok).json()["deleted"] == "主队偏好"
    # 未登录 401
    assert client.get("/me/memories").status_code == 401


# ---------- F7：非比赛日 ----------

def test_rest_day_stream(db, client):
    date = "2026-07-15"  # 空日期
    body = client.get("/stream", params={"date": date}).json()
    assert body["mode"] == "rest_day"
    assert body["rest_day"]["course"]["minutes"] == 2
    assert body["stats"]["total"] == 0


def test_me_rest_flow(db, client):
    client.post("/auth/device", json={"device_token": "tok-rest"})
    tok = {"Authorization": "Bearer tok-rest"}
    r = client.post("/me/rest", headers=tok).json()
    assert r["rested_until"] >= today_cn()
    me = client.get("/me", headers=tok).json()
    assert me["streak"]["rested"] is True
    client.post("/me/unrest", headers=tok)
    assert client.get("/me", headers=tok).json()["rested_until"] == ""


# ---------- F15：卡片路由（意图 gate ≥85%） ----------

def test_intent_routing_accuracy():
    """F15 gate：意图准确率 ≥85%。规则集上应 100%。"""
    cases = [
        ("今晚买啥", "buy_tonight"),
        ("今晚买什么好", "buy_tonight"),
        ("有什么推荐吗", "buy_tonight"),
        ("为什么利物浦别碰", "why_not"),
        ("这场为啥不推", "why_not"),
        ("复盘一下昨天", "postmortem"),
        ("昨天为什么输", "postmortem"),
        ("帮我归因", "postmortem"),
        ("记住我的主队是曼城", "memory_write"),
        ("记一下我偏好稳健", "memory_write"),
        ("你记得我什么", "memory_query"),
        ("我的记忆有哪些", "memory_query"),
        ("我连败几场了", "protection"),
        ("今天不看了", "rest"),
        ("查：曼城", "lookup_team"),
        ("今天天气怎么样", "fallback"),
    ]
    correct = sum(1 for text, exp in cases if route_intent(text) == exp)
    accuracy = correct / len(cases)
    assert accuracy >= 0.85, f"意图准确率 {accuracy:.0%} < 85%"
    assert accuracy == 1.0


def test_chat_endpoint_with_protection_note(db, client, monkeypatch):
    _mini(monkeypatch)
    user, _ = login_device(db, "tok-chat")
    # 制造保护态
    user.discipline_on = True
    db.commit()
    for i in range(3):
        v = Verdict(id=f"chat{i}", trade_date="2026-11-03", match_id=f"c{i}",
                    match_no=f"周四00{i}", league="英超", home="A", away="B",
                    kickoff="2026-11-03 21:00:00", pool="had", goal_line="",
                    sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.6, p_draw=0.25,
                    p_away=0.15, status="promoted", gates={},
                    payload={"id": f"chat{i}", "trade_date": "2026-11-03"},
                    payload_hash="d" * 64, pick={"dir": "主胜", "prob": 0.6, "sp": 1.5, "ev": -0.1},
                    settled="lose", result_score="0-1")
        db.merge(v)
        db.add(Bet(user_id=user.id, verdict_id=f"chat{i}", amount=100, pick_dir="主胜"))
    db.commit()
    r = client.post("/chat", json={"text": "今晚买啥"},
                    headers={"Authorization": "Bearer tok-chat"}).json()
    assert r["type"] == "buy_tonight"
    assert "连败保护中" in r["text"]  # 降温尾注
    assert r["protection"]["streak"] == 3


def test_bets_only_promoted(db, client, monkeypatch):
    _mini(monkeypatch)
    _seed_match(db, "2045020", "周四020", sp=(1.20, 4.50, 9.00))  # 深水 → killed
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-bet"})
    tok = {"Authorization": "Bearer tok-bet"}
    vid = f"v{today_cn()}-周四020"
    r = client.post("/bets", json={"verdict_id": vid, "amount": 100}, headers=tok)
    assert r.status_code == 422  # 只能记已晋升判决


# ---------- W6 遗漏补齐回归 ----------

def test_stream_has_postmortems_section(db, client, monkeypatch):
    """遗漏A：流内复盘卡（已结算 promoted + 归因）。"""
    _mini(monkeypatch)
    _seed_match(db, "2045030", "周四030")
    _add_intl(db)
    build_verdicts(db, today_cn(), NOW)
    v = db.scalars(select(Verdict)).first()
    v.settled = "lose"
    v.result_score = "0-1"
    db.commit()
    body = client.get("/stream").json()
    assert "postmortems" in body and len(body["postmortems"]) >= 1
    pm = body["postmortems"][0]
    assert pm["attribution"] and pm["result_score"] == "0-1"


def test_bet_postmortem_endpoint(db, client, monkeypatch):
    """遗漏B：注单死因回访（归因 + 金额 what-if）。"""
    _mini(monkeypatch)
    _seed_match(db, "2045031", "周四031")
    _add_intl(db)
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-bpm"})
    tok = {"Authorization": "Bearer tok-bpm"}
    v = db.scalars(select(Verdict)).first()
    b = client.post("/bets", json={"verdict_id": v.id, "amount": 100}, headers=tok).json()
    v.settled = "lose"
    v.result_score = "0-1"
    db.commit()
    r = client.get(f"/bets/{b['id']}/postmortem", headers=tok).json()
    assert r["bet"]["amount"] == 100 and r["bet"]["pnl"] == -100
    assert "少亏 100" in r["whatif"]


def test_patch_me_settings(db, client):
    """遗漏C：PATCH /me（persona/昵称/赔率格式/语言 + 非法值 422）。"""
    client.post("/auth/device", json={"device_token": "tok-patch"})
    tok = {"Authorization": "Bearer tok-patch"}
    r = client.patch("/me", json={"persona": "meng", "display_name": "小码酱",
                                  "odds_format": "hk", "locale": "en"}, headers=tok).json()
    assert r["changed"] == {"display_name": "小码酱", "persona": "meng",
                            "odds_format": "hk", "locale": "en"}
    me = client.get("/me", headers=tok).json()
    assert me["persona"] == "meng" and me["streak"] is not None
    assert client.patch("/me", json={"persona": "hacker"}, headers=tok).status_code == 422


def test_delete_me_with_cooldown_restore(db, client):
    """遗漏D：注销冷静期 = 410 + 撤回；期间端点不可用（review 二轮语义修复）。"""
    client.post("/auth/device", json={"device_token": "tok-del"})
    tok = {"Authorization": "Bearer tok-del"}
    r = client.delete("/me", headers=tok).json()
    assert r["deleted"] is True and r["cooldown_days"] == 7
    # 冷静期内：认证端点 410 + 撤回指引
    me = client.get("/me", headers=tok)
    assert me.status_code == 410
    assert "撤回" in me.json()["detail"]["message"]
    # 匿名化：chat 仍可用但按匿名（optional_user 降级）
    chat = client.post("/chat", json={"text": "今晚买啥"}, headers=tok)
    assert chat.status_code == 200
    # 同令牌登录 → 撤回 → 端点恢复 200
    client.post("/auth/device", json={"device_token": "tok-del"})
    me2 = client.get("/me", headers=tok)
    assert me2.status_code == 200 and me2.json()["display_name"] is not None


def test_bets_protection_requires_confirm(db, client, monkeypatch):
    """遗漏E：保护期记注 → 423，confirm 放行（不静默拦截）。"""
    _mini(monkeypatch)
    _seed_match(db, "2045032", "周四032")
    _add_intl(db)
    build_verdicts(db, today_cn(), NOW)
    client.post("/auth/device", json={"device_token": "tok-prot"})
    tok = {"Authorization": "Bearer tok-prot"}
    v = db.scalars(select(Verdict)).first()
    # 造 3 连败
    for i in range(3):
        v0 = Verdict(id=f"prot{i}", trade_date="2026-11-03", match_id=f"p{i}",
                     match_no=f"周四90{i}", league="英超", home="A", away="B",
                     kickoff="2026-11-03 12:00:00", pool="had", goal_line="",
                     sp_h=1.5, sp_d=4.0, sp_a=6.0, rake=0.08, p_home=0.6, p_draw=0.25,
                     p_away=0.15, status="promoted", gates={},
                     payload={"id": f"prot{i}", "trade_date": "2026-11-03"},
                     payload_hash="f" * 64, pick={"dir": "主胜", "prob": 0.6, "sp": 1.5, "ev": -0.1},
                     settled="lose", result_score="0-1")
        db.merge(v0)
        db.add(Bet(user_id=client.get("/me", headers=tok).json()["user_id"],
                   verdict_id=f"prot{i}", amount=100, pick_dir="主胜"))
    db.commit()
    r = client.post("/bets", json={"verdict_id": v.id, "amount": 100}, headers=tok)
    assert r.status_code == 423 and "连败" in r.json()["detail"]["message"]
    r2 = client.post("/bets", json={"verdict_id": v.id, "amount": 100, "confirm": True},
                     headers=tok)
    assert r2.status_code == 200  # 显式确认后放行（自主权）


def test_chat_memory_write_lands(db, client):
    """遗漏F：chat 直接写记忆 + 冲突必问。"""
    client.post("/auth/device", json={"device_token": "tok-cmw"})
    tok = {"Authorization": "Bearer tok-cmw"}
    r = client.post("/chat", json={"text": "记住我的主队是曼城"},
                    headers=tok).json()
    assert r["memory"]["key"] == "主队偏好" and r["memory"]["status"] == "created"
    # 冲突：chat 内必问
    r2 = client.post("/chat", json={"text": "记住我的主队是利物浦"},
                     headers=tok).json()
    assert "conflict" in r2 and "绝不静默覆盖" in r2["text"]
    ms = client.get("/me/memories", headers=tok).json()
    assert {m["value"] for m in ms if m["key"] == "主队偏好"} == {"曼城"}  # 未被覆盖


def test_stream_postmortems_cross_day(db, client, monkeypatch):
    """review 二轮：流内复盘卡跨日可见（昨天的结算今天必须看到）。"""
    _mini(monkeypatch)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # 昨天的已结算败局（不经 build_verdicts 窗口，直接落行）
    v = Verdict(id="pm-yesterday", trade_date=yesterday, match_id="y1",
                match_no="周一090", league="英超", home="霸主", away="弱旅",
                kickoff=f"{yesterday} 21:00:00", pool="had", goal_line="",
                sp_h=1.4, sp_d=4.6, sp_a=7.0, rake=0.069, p_home=0.62, p_draw=0.21,
                p_away=0.17, status="promoted", gates={},
                payload={"id": "pm-yesterday", "trade_date": yesterday,
                         "model": {"raw": [0.62, 0.21, 0.17]}},
                payload_hash="9" * 64,
                pick={"dir": "主胜", "prob": 0.66, "sp": 1.4, "ev": -0.07},
                settled="lose", result_score="0-1")
    db.merge(v)
    db.commit()
    body = client.get("/stream").json()  # 今天的流
    pm_ids = [p["verdict_id"] for p in body.get("postmortems", [])]
    assert "pm-yesterday" in pm_ids, "昨天的复盘卡今天必须可见"
    assert body["postmortems"][0]["attribution"] in ("高置信落空", "随机波动")


def test_killed_outcomes_seven_day_window(db):
    """review 二轮：killed 统计口径 = 近 7 天（老数据不计入）。"""
    from app.modules.postmortem import killed_outcomes
    old_date = "2026-01-01"  # 远超 7 天
    v = Verdict(id="kill-old", trade_date=old_date, match_id="ko", match_no="old",
                league="英超", home="A", away="B", kickoff=f"{old_date} 21:00:00",
                pool="had", goal_line="", sp_h=1.2, sp_d=4.5, sp_a=9.0, rake=0.143,
                p_home=0.71, p_draw=0.19, p_away=0.10, status="killed",
                gates={"price": {"result": "fail", "detail": {}}},
                payload={"id": "kill-old", "trade_date": old_date},
                payload_hash="7" * 64, settled="lose", result_score="0-2")
    db.merge(v)
    db.commit()
    ko = killed_outcomes(db, days=7)
    assert ko["killed_total"] == 0  # 老数据不入 7 天口径
    assert ko["avoided_loss_cny"] == 0
