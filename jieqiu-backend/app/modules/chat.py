"""F15 卡片路由（W6 v0.5：规则意图；LLM 意图 v1.5 接入同一接口）。

route_intent(text) -> intent —— 纯函数，意图准确率 gate（≥85%）由此测试。
respond() 把意图映射到卡片 + 人设语气文本。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from sqlalchemy import select

from ..features.recommendations.service import today as recommendations_today
from ..models import SPMatch, User, Verdict
from .postmortem import postmortem
from .timeutil import trade_date_now
from .users import list_memories, user_streak

log = logging.getLogger(__name__)

# 意图关键词（优先级从上到下）
_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("memory_write", ("记住", "记一下", "我的主队", "我是", "偏好")),
    ("memory_query", ("记得我", "记得什么", "我的记忆", "你记得")),
    ("postmortem", ("复盘", "归因", "为什么输", "昨天怎么样", "总结")),
    ("why_not", ("为什么不", "别碰", "死因", "为啥不推", "为什么不推")),
    ("rest", ("今天不看了", "不想看了", "休息", "今天到此为止")),
    ("protection", ("连败", "保护", "降温")),
    ("analyze_match", ("分析", "这场", "依据")),
    ("lookup_team", ("查：", "查一下", "怎么看")),
    ("buy_tonight", ("今晚买啥", "今晚买什么", "今晚看哪场", "今晚看什么", "看哪场",
                     "今日预测", "有什么预测", "看预测", "有什么推荐", "买啥", "推一场")),
]


def route_intent(text: str) -> str:
    t = (text or "").strip().lower()
    for intent, kws in _INTENT_RULES:
        if any(kw in t for kw in kws):
            return intent
    if any(ch.isdigit() or "周" in t for ch in t) and ("vs" in t or "对" in t):
        return "lookup_match"
    return "fallback"


def _resolve_match(db: Session, text: str, match_id: str) -> SPMatch | None:
    if match_id:
        return db.get(SPMatch, match_id)
    today = trade_date_now()
    rows = list(db.scalars(select(SPMatch).where(
        SPMatch.kickoff.like(f"{today}%"))).all())
    for row in rows:
        if (row.home and row.home in text) or (row.away and row.away in text):
            return row
    return None


def _analysis_text(analysis: dict) -> str:
    if analysis.get("status") != "ready":
        reason = analysis.get("reason") or "unavailable"
        if reason == "coverage":
            missing = "、".join(analysis.get("missing") or [])
            return f"这场数据还不够（缺 {missing or '关键来源'}），先不生成 AI 解读。"
        if reason == "not_configured":
            return "AI 解读还没配置 deep 模型；先看三关和数据。"
        return f"AI 解读暂不可用（{reason}）。"
    parts = [analysis.get("summary") or ""]
    factors = analysis.get("key_factors") or []
    risks = analysis.get("risks") or []
    invalidators = analysis.get("invalidators") or []
    gaps = analysis.get("data_gaps") or []
    if factors:
        parts.append("关键：" + "；".join(factors[:3]))
    if risks:
        parts.append("风险：" + "；".join(risks[:2]))
    if invalidators:
        parts.append("失效：" + "；".join(invalidators[:2]))
    if gaps:
        parts.append("数据缺口：" + "；".join(gaps[:2]))
    return "\n".join(p for p in parts if p)[:900]


def respond(db: Session, user: User | None, text: str,
            session_id: str = "", match_id: str = "") -> dict:
    """意图 → 卡片 + 文案。所有卡片都是真实数据驱动。"""
    intent = route_intent(text)
    card: dict = {"type": intent}

    if intent == "analyze_match" or (match_id and intent in ("lookup_team", "fallback")):
        match = _resolve_match(db, text, match_id)
        if match is not None:
            from ..features.analysis import service as analysis_service
            analysis = analysis_service.generate(db, match.match_id)
            card.update({
                "type": "match_analysis",
                "match_id": match.match_id,
                "analysis_status": analysis.get("status"),
                "analysis_reason": analysis.get("reason"),
                "analysis": analysis if analysis.get("status") == "ready" else None,
                "text": _analysis_text(analysis),
            })
            return card
        card["type"] = "fallback"
        card["text"] = "要分析哪一场？先在首页选中比赛，或直接说“分析：曼城 vs 布莱顿”。"
        return card

    if intent == "buy_tonight":
        # 只回答已发布判断：raw promoted 还没过发布门，不能当成推荐。
        # 日期必须用竞彩日（05:00 边界），不能用日历日，否则凌晨会查空。
        published = recommendations_today(db, trade_date_now()).get("snapshots") or []
        top = published[0] if published else None
        verdict = (top or {}).get("verdict") or {}
        if top:
            pick = verdict.get("pick") or {}
            card["verdict_id"] = verdict.get("id")
            card["pick"] = pick
            card["hash"] = top.get("payload_hash")
            card["text"] = (f"{verdict.get('home')} vs {verdict.get('away')}：三关全过，已发布。"
                            f"详情与封存哈希见卡片。")
        else:
            card["text"] = "今晚还没有已发布的预测——没有就不推，这是纪律。"

    elif intent == "why_not":
        killed = db.scalars(
            select(Verdict).where(Verdict.status == "killed",
                                  Verdict.trade_date == trade_date_now())
            .order_by(Verdict.rake.desc()).limit(1)
        ).first()
        if killed:
            card["verdict_id"] = killed.id
            card["dead_gate"] = next((g for g in ("price", "market", "model")
                                      if killed.gates.get(g, {}).get("result") == "fail"), None)
            card["text"] = f"最近没给预测的是 {killed.home} vs {killed.away}，原因见卡片。"
        else:
            card["text"] = "今日暂无未给预测的场次记录。"

    elif intent == "memory_write":
        if user is None:
            card["text"] = "登录后我才能记住（PUT /me/memories）。"
            return card
        import re
        m = re.search(r"记住(?:我的)?(.+?)(?:是|叫|：|:)\s*(.+)", text.strip())
        if not m:
            card["text"] = "这样说我就懂：「记住我的主队是曼城」。"
            return card
        raw_key = m.group(1).strip()
        key = ("主队偏好" if "主队" in raw_key else
               "风险偏好" if ("偏好" in raw_key or "风格" in raw_key) else raw_key[:64])
        value = m.group(2).strip().strip("。.！!")
        from .users import upsert_memory
        mem, status = upsert_memory(db, user.id, key, value)
        if status == "conflict":
            old = next((x.value for x in list_memories(db, user.id) if x.key == key), "")
            card["conflict"] = {"key": key, "existing": old, "incoming": value}
            card["text"] = (f"我记的「{key}」是「{old}」，你现在说是「{value}」——"
                            "要覆盖吗？确认后我才会改，绝不静默覆盖。")
        else:
            card["memory"] = {"key": key, "value": value, "status": status}
            card["text"] = (f"记住了：{key} = {value}。" if status == "created"
                            else f"已更新：{key} = {value}。")

    elif intent == "memory_query":
        ms = list_memories(db, user.id) if user else []
        card["memories"] = [{"key": m.key, "value": m.value, "source": m.source} for m in ms]
        card["text"] = (f"我记得 {len(ms)} 条。" if ms else "我还没记住关于你的事。")

    elif intent == "postmortem":
        v = db.scalars(
            select(Verdict).where(Verdict.settled.isnot(None)).order_by(Verdict.kickoff.desc()).limit(1)
        ).first()
        if v:
            card["verdict_id"] = v.id
            card["postmortem"] = postmortem(v)
            card["text"] = card["postmortem"].get("attribution", {}).get("note", "复盘见卡片。")
        else:
            card["text"] = "还没有已结算的判决可复盘。"

    elif intent == "rest":
        card["text"] = "好。走 POST /me/rest（需登录），明晚 19:02 结论照常等你。"

    elif intent == "protection":
        if user:
            st = user_streak(db, user)
            card["streak"] = st
            card["text"] = (f"当前连败 {st['streak']} 场，保护"
                            f"{'已触发：建议今天只看不下。' if st['active'] else '未触发。'}")
        else:
            card["text"] = "登录后我可以按你的注单计算连败保护。"

    elif intent == "lookup_team":
        team = text.split("：")[-1].split(":")[-1].strip()
        rows = db.scalars(
            select(Verdict).where(Verdict.home.contains(team) | Verdict.away.contains(team))
            .order_by(Verdict.trade_date.desc()).limit(1)
        ).first()
        if rows:
            card["verdict_id"] = rows.id
            card["gates"] = {k: g["result"] for k, g in rows.gates.items()}
            card["text"] = f"{rows.home} vs {rows.away}（{rows.trade_date}）：状态 {rows.status}。"
        else:
            card["text"] = f"没找到关于「{team}」的近期判决。"

    elif intent == "lookup_match":
        card["text"] = "报「查：队名」我可以定位到具体判决。"

    else:  # fallback
        card["text"] = ("我聊今日预测、为什么不出、你的复盘和记忆。"
                        "试试：今日预测 / 为什么不出 / 复盘 / 记住我的主队是曼城。")
        # 匿名用户固定引导（0 LLM）；登录后跑题/开放问题才进入 fast。
        if user is not None:
            from .llm_gateway import complete
            try:
                res = complete(
                    db, "open_chat",
                    [{"role": "system",
                      "content": ("你是球多多赛前分析助理。只聊足球数据、预测依据、"
                                  "成本与风险纪律；可以解释已给出的方向与概率，但不得改写"
                                  "概率、不得编造未提供的事实、不承诺收益、不引导加注。"
                                  "回答不超过 120 字，事实不确定就直说不知道。")},
                     {"role": "user", "content": text}],
                    max_tokens=220, user_id=user.id, session_id=session_id,
                )
            except Exception:  # noqa: BLE001 - 网关异常也不能阻塞 /chat
                log.exception("llm fallback failed")
                res = None
            if res is not None and not res.degraded and res.text:
                from .compliance import scan_text
                hits = scan_text(res.text)
                if hits:
                    card["llm"] = {"filtered": hits}
                else:
                    card["text"] = res.text.strip()[:800]
                    card["llm"] = {"profile": res.profile, "model": res.model,
                                   "cached": res.cached}

    # 保护中的用户：所有回复追加降温尾注（F11 行为面）
    if user:
        st = user_streak(db, user)
        if st["active"]:
            card["protection"] = st
            card["text"] += "（连败保护中：今天建议只看不下。）"
    return card
