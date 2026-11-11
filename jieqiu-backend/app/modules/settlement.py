"""90 分钟赛果结算与市场结算事实。

规则：
- 1X2 / 让球 / 大小球 / BTTS / 正确比分：FT90，不含加时点球；
- 半全场：HT + FT90；
- 先进球：需要事件顺序，当前结果表没有时保持 pending；
- AET/PEN 只能用于晋级类市场，不能拿去结算 1X2。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MatchResult, MarketSettlement, Verdict, utcnow

CN = timezone(timedelta(hours=8))
RULES_VERSION = "v1"


def _ft(result: MatchResult) -> tuple[int, int] | None:
    if result.ft_home is not None and result.ft_away is not None:
        return int(result.ft_home), int(result.ft_away)
    # 兼容旧数据：旧 goals_home/away 可能是 FT，也可能含加时；
    # 只有明确 status=FT 时才允许回退，避免把 AET/PEN 当 90 分钟。
    if (result.status or "FT").upper() in ("FT", "FINISHED"):
        return int(result.goals_home), int(result.goals_away)
    return None


def _ht(result: MatchResult) -> tuple[int, int] | None:
    if result.ht_home is not None and result.ht_away is not None:
        return int(result.ht_home), int(result.ht_away)
    return None


def _norm_dir(value: str) -> str:
    v = (value or "").strip().lower()
    return {
        "主胜": "home", "主": "home", "home": "home",
        "平局": "draw", "平": "draw", "draw": "draw",
        "客胜": "away", "客": "away", "away": "away",
        "大": "over", "大球": "over", "over": "over",
        "小": "under", "小球": "under", "under": "under",
        "是": "yes", "yes": "yes", "否": "no", "no": "no",
    }.get(v, v)


def outcome(market: str, line: str, direction: str,
            ft: tuple[int, int], ht: tuple[int, int] | None = None) -> tuple[str, bool | None] | None:
    """返回 (result_label, won)；None 表示无法结算。"""
    market = (market or "had").lower()
    direction = _norm_dir(direction)
    gh, ga = ft
    if market == "had":
        actual = "home" if gh > ga else "draw" if gh == ga else "away"
        return actual, actual == direction
    if market == "hhad":
        try:
            line_val = float(line or 0)
        except ValueError:
            line_val = 0.0
        adj = gh - ga + line_val
        actual = "home" if adj > 0 else "draw" if adj == 0 else "away"
        return actual, actual == direction
    if market in ("ou", "totals"):
        try:
            line_val = float(line)
        except (TypeError, ValueError):
            return None
        total = gh + ga
        actual = "over" if total > line_val else "under" if total < line_val else "push"
        if actual == "push":
            return "push", None
        return actual, actual == direction
    if market == "btts":
        actual = "yes" if gh > 0 and ga > 0 else "no"
        return actual, actual == direction
    if market == "htft":
        if ht is None:
            return None
        hh, ha = ht
        ht_res = "home" if hh > ha else "draw" if hh == ha else "away"
        ft_res = "home" if gh > ga else "draw" if gh == ga else "away"
        actual = f"{ht_res}/{ft_res}"
        wanted = direction.replace("主", "home").replace("平", "draw").replace("客", "away")
        return actual, actual == wanted
    if market in ("cs", "correct_score"):
        actual = f"{gh}-{ga}"
        return actual, actual == (direction or "").replace(":", "-").strip()
    # first_goal 需要事件顺序；没有事件时绝不猜。
    return None


def _find_result(db: Session, v: Verdict) -> MatchResult | None:
    try:
        ko = datetime.strptime(v.kickoff, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    for offset in (0, 1):
        euro_date = (ko - timedelta(days=offset)).strftime("%Y-%m-%d")
        row = db.scalar(select(MatchResult).where(
            MatchResult.home == v.home, MatchResult.away == v.away,
            MatchResult.match_date == euro_date))
        if row is not None:
            return row
    return None


def _fill_clv(db: Session, v: Verdict) -> None:
    """复用旧结算的 CLV 计算；失败不影响结算。"""
    try:
        from .settle import _fill_clv as legacy_fill
        legacy_fill(db, v)
    except Exception:
        pass


def settle_verdict(db: Session, v: Verdict, result: MatchResult) -> int:
    """结算一条 Verdict 的 had/hhad 市场，并写 MarketSettlement。"""
    ft = _ft(result)
    if ft is None:
        return 0
    market = "hhad" if v.pool == "hhad" else "had"
    line = v.goal_line if market == "hhad" else ""
    direction = (v.pick or {}).get("dir", "")
    if not direction:
        return 0
    out = outcome(market, line, direction, ft, _ht(result))
    if out is None:
        return 0
    actual, won = out
    v.settled = "void" if won is None else ("win" if won else "lose")
    v.result_score = f"{ft[0]}-{ft[1]}"
    v.settled_at = utcnow()
    _fill_clv(db, v)
    key = (v.id, market, line, direction, RULES_VERSION)
    row = db.scalar(select(MarketSettlement).where(
        MarketSettlement.subject_type == "verdict",
        MarketSettlement.subject_id == v.id,
        MarketSettlement.leg_index == 0,
        MarketSettlement.market == market,
        MarketSettlement.line == line,
        MarketSettlement.direction == direction,
        MarketSettlement.rules_version == RULES_VERSION,
    ))
    if row is None:
        row = MarketSettlement(
            subject_type="verdict", subject_id=v.id, leg_index=0,
            market=market, line=line, direction=direction,
            rules_version=RULES_VERSION,
        )
        db.add(row)
    row.result = actual
    row.won = won
    row.source = result.source or ""
    row.settled_at = utcnow()
    return 1


def settle_pending(db: Session, trade_date: str | None = None) -> int:
    """独立结算任务：不依赖赛果是否刚插入。"""
    from . import ops
    job_id = ops.job_start(db, "settle_pending")
    try:
        q = select(Verdict).where(Verdict.pick.isnot(None), Verdict.settled.is_(None))
        if trade_date:
            q = q.where(Verdict.trade_date == trade_date)
        else:
            cutoff = (datetime.now(CN) - timedelta(days=30)).strftime("%Y-%m-%d")
            q = q.where(Verdict.trade_date >= cutoff)
        n = 0
        for v in db.scalars(q).all():
            result = _find_result(db, v)
            if result is not None:
                n += settle_verdict(db, v, result)
        if n:
            db.commit()
        ops.job_finish(db, job_id, "ok")
        return n
    except Exception as exc:
        db.rollback()
        ops.job_finish(db, job_id, "error", f"{type(exc).__name__}: {exc}")
        ops.exception(db, "settlement_error", str(exc), severity=3,
                      source="settle_pending", dedupe_key="settlement_error")
        return 0
