"""F12 归因 + what-if + 周报。

归因规则（确定性，可抽检验证 ≥90%）：
- 未结算/未推 → 复述状态，不做归因
- lose 且封存时市闸 pending → 「信息不足」
- lose 且 pick 概率 ≥ 60% → 「高置信落空（随机波动）」
- lose 且收缩前模型与市场偏差 > 8pp → 「强预测落空（曾大幅偏离市场）」
- 其余 lose → 「随机波动」
- win → 「预测兑现」，附是否收缩触发（侥幸/实力标注）

what-if（诚实口径）：
- 用户注单 realized P&L
- 被砍场次的真实结局统计（砍对的 / 砍错的都公开）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Bet, Verdict

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


def attribute(v: Verdict) -> dict:
    """对已结算判决归因。win/lose 都给；未结算返回 status-only。"""
    if v.settled is None:
        return {"settled": False, "class": None, "note": "赛果未出，不作归因"}
    if v.settled == "win":
        shrunk = (v.payload or {}).get("model", {}).get("shrunk") or [0, 0, 0]
        top = max(shrunk)
        return {"settled": True, "class": "预测兑现",
                "note": f"中奖（{v.result_score}）。收缩后置信 {top*100:.1f}%。"}
    gates = v.gates or {}
    market_pending = gates.get("market", {}).get("result") == "pending_data"
    pick_prob = (v.pick or {}).get("prob", 0.0)
    deviation = _pre_shrink_deviation(v)
    if market_pending:
        return {"settled": True, "class": "信息不足",
                "note": "封存时国际盘缺席（单源复核），市场一致性未验证。"}
    if deviation is not None and deviation > 0.08:
        return {"settled": True, "class": "强预测落空",
                "note": f"模型曾偏离市场 {deviation*100:.1f}pp（收缩纪律已减半），本次偏离未兑现。"}
    if pick_prob >= 0.60:
        return {"settled": True, "class": "高置信落空",
                "note": f"置信 {pick_prob*100:.1f}% 仍落——随机波动，注意长期样本而非单场。"}
    return {"settled": True, "class": "随机波动",
            "note": f"置信 {pick_prob*100:.1f}% 的预测，结果落在少数侧——正常。"}

def _pre_shrink_deviation(v: Verdict) -> float | None:
    """收缩前模型概率（payload.model.raw 若有）与市场去水的最大偏差。"""
    raw = (v.payload or {}).get("model", {}).get("raw")
    if not raw:
        return None
    market = [v.p_home, v.p_draw, v.p_away]
    return max(abs(a - b) for a, b in zip(raw, market))


def postmortem(v: Verdict) -> dict:
    """复盘卡：状态 → 死因/归因 → what-if。"""
    base = {
        "id": v.id,
        "match_no": v.match_no,
        "match": f"{v.home} vs {v.away}",
        "trade_date": v.trade_date,
        "pool": v.pool,
        "goal_line": v.goal_line,
        "pick": v.pick,
        "status": v.status,
        "settled": v.settled,
        "result_score": v.result_score,
    }
    if v.status == "killed":
        dead = next((g for g in ("price", "market", "model")
                     if (v.gates.get(g, {}).get("result") == "fail")), None)
        base["kind"] = "killed"
        base["dead_gate"] = dead
        base["why"] = (v.gates.get(dead, {}).get("detail") or {})
        base["whatif"] = "该场未推——结算后无论中不中，都不影响你的账户。"
        return base
    if v.status == "screening":
        base["kind"] = "screening"
        base["whatif"] = "未推未结算。"
        return base
    base["kind"] = "promoted"
    base["attribution"] = attribute(v)
    base["whatif"] = _whatif_promoted(v)
    return base


def _whatif_promoted(v: Verdict) -> str:
    if v.settled == "win":
        return "中了。预测与成本账都在封存里可复算。"
    if v.settled == "lose":
        return (f"未中（{v.result_score}）。若下注 100 元，本次亏损 100 元——"
                "这类场次长期按置信概率兑现，单场落空已在预期内。")
    return "赛果未出。"


def killed_outcomes(db: Session, days: int = 7) -> dict:
    """被砍场的真实结局（诚实公开：砍对/砍错都给）。口径与周报一致（近 N 天）。"""
    cutoff_date = (datetime.now(CN) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.execute(
        select(Verdict.trade_date, Verdict.settled)
        .where(Verdict.status == "killed", Verdict.trade_date >= cutoff_date)
    ).all()
    recent = [(d, s) for d, s in rows if _within_days(d, days)]
    settled = [s for _d, s in recent if s]
    lose = sum(1 for s in settled if s == "lose")
    win = len(settled) - lose
    return {
        "range_days": days,
        "killed_total": len(recent),
        "settled": len(settled),
        "would_lose": lose,      # 砍对（避损）场次
        "would_win": win,        # 砍错（机会成本）场次 —— 公开
        "avoided_loss_cny": lose * 100,   # 假设每注 100 跟买的避免损失
        "missed_win_cny": win * 100,      # 对称披露机会成本
    }


def weekly_report(db: Session, user_id: str | None = None) -> dict:
    """周报：近 7 天判决汇总 + 归因分布 + 砍场诚实披露 + 用户注单 P&L（可选）。"""
    today = datetime.now(CN).strftime("%Y-%m-%d")
    cutoff_date = (datetime.now(CN) - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = db.scalars(
        select(Verdict).where(Verdict.trade_date >= cutoff_date,
                              Verdict.trade_date <= today)
        .order_by(Verdict.trade_date.desc())).all()
    recent = [v for v in rows if _within_days(v.trade_date, 7)]
    promoted = [v for v in recent if v.status == "promoted"]
    settled = [v for v in promoted if v.settled]
    attr = {}
    for v in settled:
        a = attribute(v)["class"]
        attr[a] = attr.get(a, 0) + 1
    clv_rows = [v for v in settled if v.clv is not None]
    out = {
        "range_days": 7,
        "verdicts_total": len(recent),
        "promoted": len(promoted),
        "settled": len(settled),
        "wins": sum(1 for v in settled if v.settled == "win"),
        "attribution": attr,
        "killed": killed_outcomes(db),
        "clv": {
            "n": len(clv_rows),
            "avg": round(sum(v.clv for v in clv_rows) / len(clv_rows), 6)
            if clv_rows else None,
            "positive": sum(1 for v in clv_rows if v.clv > 0),
        },
    }
    if user_id:
        from .users import bet_pnl
        all_bets = db.scalars(select(Bet).where(Bet.user_id == user_id)).all()
        vmap = {v.id: v for v in rows}
        # 周报只统计近 7 天窗口内的注单，不能拿累计注数冒充“本周”。
        bets = [b for b in all_bets if b.verdict_id in vmap]
        settled_bets = [(b, vmap[b.verdict_id]) for b in bets if vmap[b.verdict_id].settled]
        pnl = sum((bet_pnl(b, v) or 0) for b, v in settled_bets)
        bet_clv = []
        for bet, verdict in settled_bets:
            if (verdict.clv is not None
                    and (bet.pick_dir or "") == ((verdict.pick or {}).get("dir") or "")):
                bet_clv.append(verdict.clv)
        out["you"] = {
            "bets": len(bets),
            "settled_bets": len(settled_bets),
            "pnl": round(pnl, 2),
            "clv_n": len(bet_clv),
            "clv_avg": round(sum(bet_clv) / len(bet_clv), 6) if bet_clv else None,
            "attribution": {a: sum(1 for _, v in settled_bets
                                   if v.settled == "lose" and attribute(v)["class"] == a)
                            for a in set(attribute(v)["class"] for _, v in settled_bets
                                         if v.settled == "lose")},
        }
    return out


def _within_days(date_str: str, days: int) -> bool:
    """CN 时区口径的近 N 天预测（服务器可能非 CST，不能用本地 date.today()）。"""
    from datetime import date as _d, timedelta as _td
    try:
        y, m, d = map(int, date_str.split("-"))
        today = (datetime.now(CN) - _td(hours=4)).date()  # 04:00 前仍算前一天（竞彩日界）
        delta = (today - _d(y, m, d)).days
        return 0 <= delta <= days
    except Exception:
        return False
