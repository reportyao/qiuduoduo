"""聚焦卡 / 数据脉搏 / 客观情报的只读聚合。

原则：
- 只读现有表，不伪造数据；没有的源明确写 missing/unknown。
- 统计与闸门数字来自 verdict/model_runs；LLM 解读为 None（当前未接）。
- 展示系数只乘“数据点”，raw 永远保留。
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import (AIResearch, ApiFootballFixture, Bet, IntlOdds, MatchInjury,
                       MatchLineup, MatchResult, ModelRun, SPMatch, SPSnapshot,
                       SportmonksFixtureIntel, SportmonksMatchData,
                       SportmonksPrediction, TeamStanding, User, Verdict,
                       VerdictRevision, WatchTarget)
from ...modules.intel_research import effective_status
from ...modules.intl_odds import sources_for_match
from ...modules.sportmonks import market_is_fresh
from ...modules.timeutil import CN, trade_date_from_kickoff, trade_date_now, trade_window
from ...modules.users import user_streak
from ..compliance import service as compliance_service

PERSONAS = {"zhuanjia", "laopao", "meng"}

_PULSE_CACHE: dict[str, tuple[float, dict]] = {}
_PULSE_TTL = 30.0
_PULSE_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(CN)


def _parse_cn(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(CN)
        return dt.replace(tzinfo=CN)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
    except (TypeError, ValueError):
        return None


def _in_window(value: str | None, date: str,
               start: str | None = None, end: str | None = None) -> bool:
    """轻量窗口判断：ISO 字符串前 19 位做字典序比较，避免每行 strptime。"""
    if start is None or end is None:
        start, end = trade_window(date)
    text = str(value or "")[:19].replace("T", " ")
    if not text:
        return False
    return start <= text <= end


def _minutes_until(value: str | None, now: datetime) -> int | None:
    dt = _parse_cn(value)
    if dt is None:
        return None
    return max(0, int((dt - now).total_seconds() // 60))


def _hours_until(value: str | None, now: datetime) -> int | None:
    dt = _parse_cn(value)
    if dt is None:
        return None
    return max(0, int((dt - now).total_seconds() // 3600))


def _matches_for_date(db: Session, date: str) -> list[SPMatch]:
    start, end = trade_window(date)
    return list(db.scalars(
        select(SPMatch).where(SPMatch.kickoff >= start, SPMatch.kickoff <= end)
        .order_by(SPMatch.kickoff)
    ).all())


def _latest_verdict(db: Session, match_id: str, date: str | None = None) -> Verdict | None:
    q = select(Verdict).where(Verdict.match_id == match_id)
    if date:
        q = q.where(Verdict.trade_date == date)
    return db.scalar(q.order_by(Verdict.trade_date.desc()).limit(1))


def _gate_results(v: Verdict) -> dict:
    return {k: (g.get("result") if isinstance(g, dict) else str(g))
            for k, g in (v.gates or {}).items()}


def _card(v: Verdict) -> dict:
    return {
        "id": v.id, "status": v.status, "tier": v.tier,
        "model_status": v.model_status, "model_source": v.model_source,
        "pick": v.pick if v.tier != "market_reference" else None,
        "rake": v.rake, "rake_threshold": v.rake_threshold,
        "probs": {"home": v.p_home, "draw": v.p_draw, "away": v.p_away},
        "model": (v.payload or {}).get("model"),
        "gates": _gate_results(v),
        "payload_hash": v.payload_hash,
        "sealed": v.sealed_at is not None,
    }


def _form(db: Session, team: str, limit: int = 5) -> dict:
    rows = list(db.scalars(
        select(MatchResult).where((MatchResult.home == team) | (MatchResult.away == team))
        .order_by(MatchResult.match_date.desc()).limit(limit)
    ).all())
    results = []
    for r in rows:
        if r.home == team:
            results.append("W" if r.goals_home > r.goals_away else "D" if r.goals_home == r.goals_away else "L")
        else:
            results.append("W" if r.goals_away > r.goals_home else "D" if r.goals_away == r.goals_home else "L")
    return {"matches": len(results), "results": results,
            "source": rows[0].source if rows else None,
            "captured_at": rows[0].retrieved_at if rows else None}


def _h2h(db: Session, home: str, away: str, limit: int = 5) -> dict:
    rows = list(db.scalars(
        select(MatchResult).where(
            ((MatchResult.home == home) & (MatchResult.away == away))
            | ((MatchResult.home == away) & (MatchResult.away == home))
        ).order_by(MatchResult.match_date.desc()).limit(limit)
    ).all())
    return {"matches": len(rows), "source": "football-data",
            "captured_at": rows[0].retrieved_at if rows else None,
            "items": [f"{r.match_date} {r.home} {r.goals_home}-{r.goals_away} {r.away}" for r in rows]}


def _rest_days(db: Session, team: str, kickoff: str) -> int | None:
    current = _parse_cn(kickoff)
    if current is None:
        return None
    prev = db.scalar(
        select(SPMatch).where(
            ((SPMatch.home == team) | (SPMatch.away == team)),
            SPMatch.kickoff < kickoff,
        ).order_by(SPMatch.kickoff.desc()).limit(1)
    )
    if prev is None:
        return None
    prev_dt = _parse_cn(prev.kickoff)
    return max(0, int((current - prev_dt).total_seconds() // 86400)) if prev_dt else None


def _latest_snapshot(db: Session, match_id: str) -> SPSnapshot | None:
    return db.scalar(
        select(SPSnapshot).where(SPSnapshot.match_id == match_id)
        .order_by(SPSnapshot.captured_at.desc()).limit(1)
    )


def _has_model(v: Verdict | None) -> bool:
    if v is None:
        return False
    if v.pick:
        return True
    model = (v.payload or {}).get("model") or {}
    return bool(model.get("shrunk") or model.get("raw") or model.get("pick"))


def _model_covered(db: Session, match_id: str, date: str, v: Verdict | None) -> bool:
    if _has_model(v):
        return True
    row = db.scalar(
        select(ModelRun).where(ModelRun.match_id == match_id,
                               ModelRun.run_date == date,
                               ModelRun.gate == "model")
        .order_by(ModelRun.id.desc()).limit(1)
    )
    return bool(row and row.result != "pending_data")


def _age_seconds(value: str | None, now: datetime) -> int | None:
    dt = _parse_cn(value)
    if dt is None:
        return None
    return max(0, int((now - dt).total_seconds()))


def _age_utc(value: str | None, now: datetime) -> int | None:
    """DB DateTime 按项目约定存 naive UTC；API-Football synced_at 用这个。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((now.astimezone(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()))


def _af_fixture(db: Session, match_id: str) -> ApiFootballFixture | None:
    return db.scalar(select(ApiFootballFixture)
                     .where(ApiFootballFixture.match_id == match_id)
                     .order_by(ApiFootballFixture.kickoff_utc.desc()).limit(1))


def _lineups(db: Session, match_id: str) -> list[MatchLineup]:
    return list(db.scalars(select(MatchLineup)
                           .where(MatchLineup.match_id == match_id)
                           .order_by(MatchLineup.side)).all())


def _injuries(db: Session, match_id: str) -> list[MatchInjury]:
    return list(db.scalars(select(MatchInjury)
                           .where(MatchInjury.match_id == match_id)
                           .order_by(MatchInjury.team_name, MatchInjury.player_name)).all())


def _standings(db: Session, fixture: ApiFootballFixture | None) -> list[TeamStanding]:
    if fixture is None:
        return []
    ids = [fixture.home_team_id, fixture.away_team_id]
    return list(db.scalars(select(TeamStanding).where(
        TeamStanding.league_id == fixture.league_id,
        TeamStanding.season == fixture.season,
        TeamStanding.team_id.in_(ids))).all())


def _coverage(db: Session, match: SPMatch, date: str, v: Verdict | None,
              snap: SPSnapshot | None, intl: list[IntlOdds], now: datetime) -> dict:
    model_ok = _model_covered(db, match.match_id, date, v)
    price_present = bool(snap or v)
    schedule_ok = bool(match.kickoff)
    price_age = _age_seconds(snap.captured_at, now) if snap else None
    market_age = min((_age_seconds(r.retrieved_at, now) for r in intl
                      if _age_seconds(r.retrieved_at, now) is not None), default=None)
    price_ok = price_present and price_age is not None and price_age <= 15 * 60
    sm = db.get(SportmonksMatchData, match.match_id)
    sm_ok = bool(sm is not None and sm.probs and market_is_fresh(sm))
    sm_age = _age_seconds(sm.captured_at, now) if sm and sm.captured_at else None
    intl_ok = bool(intl) and market_age is not None and market_age <= 15 * 60
    market_ok = intl_ok or sm_ok
    last_market = max(
        [r.retrieved_at for r in intl if r.retrieved_at]
        + ([sm.captured_at.isoformat()] if sm and sm.captured_at else []),
        default=None)
    market_age = min([age for age in (market_age, sm_age) if age is not None],
                     default=None)
    fixt = _af_fixture(db, match.match_id)
    sm_intel = db.get(SportmonksFixtureIntel, match.match_id)
    sm_payload = (sm_intel.payload or {}) if sm_intel else {}
    sm_lineups = sm_payload.get("lineups") or {}
    sm_lineup_ok = bool(
        ((sm_lineups.get("home") or {}).get("starters")
         and (sm_lineups.get("away") or {}).get("starters")))
    sm_intel_age = _age_utc(sm_intel.captured_at.isoformat(), now) if sm_intel else None
    sm_lineup_ok = sm_lineup_ok and sm_intel_age is not None and sm_intel_age <= 6 * 3600
    sm_standings = sm_payload.get("standings") or {}
    sm_standings_ok = bool(sm_standings.get("home") and sm_standings.get("away"))
    sm_standings_ok = (sm_standings_ok and sm_intel_age is not None
                       and sm_intel_age <= 24 * 3600)

    lineups = _lineups(db, match.match_id)
    lineups_ok = len({r.side for r in lineups if r.starters and r.side in ("home", "away")}) == 2
    lineup_age = min((_age_utc(r.synced_at.isoformat(), now) for r in lineups
                      if r.synced_at is not None), default=None)
    lineups_ok = lineups_ok and lineup_age is not None and lineup_age <= 6 * 3600
    lineups_present = bool(lineups) or sm_lineup_ok
    lineups_ok = lineups_ok or sm_lineup_ok
    standings = _standings(db, fixt)
    standings_ids = {r.team_id for r in standings}
    standings_ok = bool(fixt and {fixt.home_team_id, fixt.away_team_id}.issubset(standings_ids))
    standings_age = min((_age_utc(r.synced_at.isoformat(), now) for r in standings
                         if r.synced_at is not None), default=None)
    standings_ok = standings_ok and standings_age is not None and standings_age <= 24 * 3600
    standings_present = bool(standings) or sm_standings_ok
    standings_ok = standings_ok or sm_standings_ok
    score = (25 if price_ok else 0) + (20 if market_ok else 0) +             (25 if model_ok else 0) + (10 if schedule_ok else 0) +             (15 if lineups_ok else 0) + (5 if standings_ok else 0)
    missing = []
    if not price_ok:
        missing.append("price")
    if not model_ok:
        missing.append("model")
    if not market_ok:
        missing.append("market")
    if not lineups_ok:
        missing.append("lineups")
    if not standings_ok:
        missing.append("standings")
    # 缺少任一必需来源时不能标 full；否则前端会显示“覆盖完整”但 deep_eligible=false。
    level = ("full" if score >= 70 and not missing else
             "partial" if score >= 50 else "insufficient")
    minutes = _minutes_until(match.kickoff, now)
    hours = _hours_until(match.kickoff, now)
    # 没有阵容数据时，距开赛 >=12h 才允许带“首发未知”做深读。
    deep = (price_ok and market_ok and model_ok and score >= 70
            and minutes is not None and minutes >= 30
            and (lineups_ok or (hours is not None and hours >= 12)))
    sm_sync = sm_intel.captured_at.isoformat() if sm_intel and sm_intel.captured_at else None
    sources = [
        {"key": "price",
         "status": "ok" if price_ok else "stale" if price_present else "missing",
         "last_sync": snap.captured_at if snap else None,
         "coverage": 1.0 if price_ok else 0.0},
        {"key": "market",
         "status": "ok" if market_ok else "stale" if (intl or sm) else "missing",
         "last_sync": last_market,
         "coverage": 1.0 if market_ok else 0.0},
        {"key": "model", "status": "ok" if model_ok else "missing",
         "last_sync": None, "coverage": 1.0 if model_ok else 0.0},
        {"key": "lineups",
         "status": "ok" if lineups_ok else "stale" if lineups_present else "missing",
         "last_sync": max(
             [value for value in
              [sm_sync] + [r.synced_at.isoformat() for r in lineups
                           if r.synced_at is not None] if value], default=None),
         "coverage": 1.0 if lineups_ok else 0.0},
        {"key": "schedule", "status": "ok" if schedule_ok else "missing",
         "last_sync": match.kickoff, "coverage": 1.0 if schedule_ok else 0.0},
        {"key": "standings",
         "status": "ok" if standings_ok else "stale" if standings_present else "missing",
         "last_sync": max(
             [value for value in
              [sm_sync] + [r.synced_at.isoformat() for r in standings
                           if r.synced_at is not None] if value], default=None),
         "coverage": 1.0 if standings_ok else 0.0},
        {"key": "sportmonks_intel",
         "status": "ok" if sm_intel else "missing",
         "last_sync": sm_sync,
         "coverage": 1.0 if sm_intel else 0.0},
    ]
    return {"score": score, "level": level, "deep_eligible": deep,
            "missing": missing, "sources": sources,
            "minutes_to_close": minutes, "hours_to_kickoff": hours}


def _facts(db: Session, match: SPMatch, v: Verdict | None, snap: SPSnapshot | None,
           intl: list[IntlOdds], now: datetime) -> tuple[list[dict], list[str]]:
    facts: list[dict] = []
    unknowns: list[str] = []
    if snap:
        facts.append({
            "id": "price", "kind": "price", "label": "竞彩官方 SP",
            "value": f"{snap.sp_h:.2f} / {snap.sp_d:.2f} / {snap.sp_a:.2f}",
            "detail": f"让球线 {snap.goal_line}" if snap.goal_line else "胜平负",
            "source": "sporttery", "captured_at": snap.captured_at,
            "status": "stale" if ((_age_seconds(snap.captured_at, now) or 0) > 15 * 60) else "confirmed",
            "confidence": 1.0,
        })
    sm = db.get(SportmonksMatchData, match.match_id)
    sm_intel = db.get(SportmonksFixtureIntel, match.match_id)
    sm_payload = (sm_intel.payload or {}) if sm_intel else {}
    sm_lineups = sm_payload.get("lineups") or {}
    sm_standings = sm_payload.get("standings") or {}
    sm_sidelined = sm_payload.get("sidelined")
    if sm is not None and sm.odds and market_is_fresh(sm):
        probs = sm.odds
        facts.append({
            "id": "market", "kind": "market",
            "label": f"Sportmonks · {sm.bookmaker or '市场'}",
            "value": (f"{float(probs.get('home', 0)) * 100:.0f}% / "
                      f"{float(probs.get('draw', 0)) * 100:.0f}% / "
                      f"{float(probs.get('away', 0)) * 100:.0f}%"),
            "detail": f"去水概率 · fixture {sm.fixture_id}",
            "source": "sportmonks",
            "captured_at": sm.captured_at.isoformat() if sm.captured_at else None,
            "status": "confirmed", "confidence": 0.9,
        })
    elif intl:
        r = intl[0]
        facts.append({
            "id": "market", "kind": "market", "label": f"国际盘 · {r.source}",
            "value": f"{r.sp_h:.2f} / {r.sp_d:.2f} / {r.sp_a:.2f}",
            "detail": f"拉取 {r.retrieved_at}", "source": r.source,
            "captured_at": r.retrieved_at,
            "status": "stale" if ((_age_seconds(r.retrieved_at, now) or 0) > 15 * 60) else "confirmed",
            "confidence": 0.9,
        })
    if _has_model(v):
        pick = v.pick or {}
        model_payload = (v.payload or {}).get("model") or {}
        prob = pick.get("prob")
        facts.append({
            "id": "model", "kind": "model", "label": "模型判断",
            "value": f"{pick.get('dir') or '待定'} · {round(float(prob or 0) * 100, 1)}%",
            "detail": "Dixon-Coles 收缩后概率；不是预测承诺",
            "source": model_payload.get("engine") or "DC v1.1",
            "captured_at": (v.payload or {}).get("data_cutoff"),
            "status": "inferred", "confidence": prob,
        })
    for side, team in (("home", match.home), ("away", match.away)):
        form = _form(db, team)
        if form["matches"]:
            facts.append({
                "id": f"form_{side}", "kind": "form", "label": f"{team} 近 {form['matches']} 场",
                "value": " ".join(form["results"]),
                "detail": "近期正式比赛战绩；样本小，只作参考",
                "source": form["source"] or "football-data",
                "captured_at": form["captured_at"], "status": "confirmed", "confidence": 0.8,
            })
    home_rest = _rest_days(db, match.home, match.kickoff)
    away_rest = _rest_days(db, match.away, match.kickoff)
    if home_rest is not None or away_rest is not None:
        facts.append({
            "id": "schedule", "kind": "schedule", "label": "休息天数",
            "value": f"{match.home} {home_rest if home_rest is not None else '—'}d · "
                     f"{match.away} {away_rest if away_rest is not None else '—'}d",
            "detail": "按竞彩赛程中的上一场计算", "source": "sporttery",
            "captured_at": match.updated_at.isoformat() if match.updated_at else None,
            "status": "confirmed", "confidence": 0.9,
        })
    h2h = _h2h(db, match.home, match.away)
    if h2h["matches"]:
        facts.append({
            "id": "h2h", "kind": "h2h", "label": "近期交锋",
            "value": f"{h2h['matches']} 场",
            "detail": "；".join(h2h["items"][:3]), "source": h2h["source"],
            "captured_at": h2h["captured_at"], "status": "confirmed", "confidence": 0.7,
        })
    fixt = _af_fixture(db, match.match_id)
    lineups = _lineups(db, match.match_id)
    injuries = _injuries(db, match.match_id)
    standings = _standings(db, fixt)
    valid_lines = [r for r in lineups if r.starters]
    if valid_lines:
        sides = {r.side: r for r in valid_lines if r.side in ("home", "away")}
        home_line = sides.get("home")
        away_line = sides.get("away")
        starters = []
        for row in (home_line, away_line):
            if row and row.starters:
                names = [p.get("name") for p in row.starters[:4] if p.get("name")]
                starters.append(f"{row.team_name or row.side}: " + "、".join(names))
        age = min((_age_utc(r.synced_at.isoformat(), now) for r in valid_lines
                   if r.synced_at is not None), default=None)
        facts.append({
            "id": "lineups", "kind": "lineup", "label": "首发",
            "value": f"{home_line.formation if home_line else '—'} / "
                     f"{away_line.formation if away_line else '—'}",
            "detail": "；".join(starters) or "首发已同步",
            "source": "API-Football",
            "captured_at": max((r.synced_at.isoformat() for r in valid_lines
                                if r.synced_at is not None), default=None),
            "status": "stale" if age is None or age > 6 * 3600 else "confirmed",
            "confidence": 0.9,
        })
    else:
        unknowns.append("首发未公布" if lineups else
                        "首发未同步" if fixt else "首发/伤停未接入")
    if injuries:
        names = "、".join(f"{r.player_name}({r.type or r.reason})" for r in injuries[:6])
        age = min((_age_utc(r.synced_at.isoformat(), now) for r in injuries
                   if r.synced_at is not None), default=None)
        facts.append({
            "id": "injuries", "kind": "injury", "label": "伤停",
            "value": f"{len(injuries)} 人",
            "detail": names, "source": "API-Football",
            "captured_at": max((r.synced_at.isoformat() for r in injuries
                                if r.synced_at is not None), default=None),
            "status": "stale" if age is None or age > 6 * 3600 else "confirmed",
            "confidence": 0.85,
        })
    elif fixt and fixt.injuries_synced_at is not None:
        age = _age_utc(fixt.injuries_synced_at.isoformat(), now)
        facts.append({
            "id": "injuries", "kind": "injury", "label": "伤停",
            "value": "无新增" if age is not None and age <= 6 * 3600 else "上次同步无记录",
            "detail": "API-Football 当前无伤停记录", "source": "API-Football",
            "captured_at": fixt.injuries_synced_at.isoformat(),
            "status": "stale" if age is None or age > 6 * 3600 else "confirmed",
            "confidence": 0.8,
        })
    else:
        unknowns.append("伤停未同步")
    if standings:
        parts = []
        for row in standings:
            parts.append(f"{row.team_name} 第{row.rank} · {row.points}分 · {row.form or '—'}")
        age = min((_age_utc(r.synced_at.isoformat(), now) for r in standings
                   if r.synced_at is not None), default=None)
        facts.append({
            "id": "standings", "kind": "standing", "label": "积分榜",
            "value": " / ".join(parts),
            "detail": "联赛排名、积分与近况；只作背景", "source": "API-Football",
            "captured_at": max((r.synced_at.isoformat() for r in standings
                                if r.synced_at is not None), default=None),
            "status": "stale" if age is None or age > 24 * 3600 else "confirmed",
            "confidence": 0.85,
        })
    else:
        unknowns.append("积分榜未同步")
    sm_cutoff = sm_intel.captured_at.isoformat() if sm_intel and sm_intel.captured_at else None
    if not valid_lines:
        home_line = sm_lineups.get("home") or {}
        away_line = sm_lineups.get("away") or {}
        if home_line.get("starters") and away_line.get("starters"):
            rows = []
            for side, line in (("home", home_line), ("away", away_line)):
                names = [p.get("name") for p in (line.get("starters") or [])[:4]
                         if p.get("name")]
                rows.append(f"{line.get('team_name') or side}: " + "、".join(names))
            facts.append({
                "id": "lineups", "kind": "lineup", "label": "首发",
                "value": f"{home_line.get('formation') or '—'} / "
                         f"{away_line.get('formation') or '—'}",
                "detail": "；".join(rows) or "Sportmonks 首发已同步",
                "source": "Sportmonks",
                "captured_at": sm_cutoff, "status": "confirmed", "confidence": 0.9,
            })
    if (not injuries and not (fixt and fixt.injuries_synced_at is not None)
            and sm_sidelined is not None):
        rows = sm_sidelined or []
        names = "、".join(f"{row.get('player_name')}（{row.get('type_label')}）"
                          for row in rows[:6] if row.get("player_name"))
        facts.append({
            "id": "injuries", "kind": "injury", "label": "伤停",
            "value": f"{len(rows)} 人" if rows else "无公开记录",
            "detail": names or "Sportmonks 当前未返回伤停名单；不代表确认全员健康",
            "source": "Sportmonks", "captured_at": sm_cutoff,
            "status": "confirmed", "confidence": 0.85,
        })
    if not standings and sm_standings.get("home") and sm_standings.get("away"):
        parts = []
        for side in ("home", "away"):
            row = sm_standings.get(side) or {}
            parts.append(
                f"{match.home if side == 'home' else match.away} 第{row.get('position')} · "
                f"{row.get('points')}分 · {' '.join(row.get('form') or []) or '—'}"
            )
        facts.append({
            "id": "standings", "kind": "standing", "label": "积分榜",
            "value": " / ".join(parts),
            "detail": "Sportmonks 小组排名、积分与近况；只作背景",
            "source": "Sportmonks", "captured_at": sm_cutoff,
            "status": "confirmed", "confidence": 0.85,
        })
    if not h2h["matches"] and sm_payload.get("h2h"):
        items = [
            f"{row.get('date')} {row.get('home')} "
            f"{row.get('score_home')}-{row.get('score_away')} {row.get('away')}"
            for row in (sm_payload.get("h2h") or [])[:3]
        ]
        facts.append({
            "id": "h2h", "kind": "h2h", "label": "近期交锋",
            "value": f"{len(sm_payload.get('h2h') or [])} 场",
            "detail": "；".join(items), "source": "Sportmonks",
            "captured_at": sm_cutoff, "status": "confirmed", "confidence": 0.8,
        })
    if not any(f.get("id", "").startswith("form_") for f in facts):
        for side in ("home", "away"):
            form = (sm_standings.get(side) or {}).get("form") or []
            if form:
                facts.append({
                    "id": f"form_{side}", "kind": "form",
                    "label": f"{match.home if side == 'home' else match.away} 近期",
                    "value": " ".join(form),
                    "detail": "Sportmonks 小组赛近况；样本小，只作参考",
                    "source": "Sportmonks", "captured_at": sm_cutoff,
                    "status": "confirmed", "confidence": 0.8,
                })
    venue = sm_payload.get("venue") or None
    if venue:
        facts.append({
            "id": "venue", "kind": "venue", "label": "场地",
            "value": f"{venue.get('name') or '—'} · {venue.get('city') or '—'}",
            "detail": f"容量 {venue.get('capacity') or '—'} · "
                      f"{venue.get('surface') or '草皮待确认'}",
            "source": "Sportmonks", "captured_at": sm_cutoff,
            "status": "confirmed", "confidence": 0.9,
        })
    weather = sm_payload.get("weather") or None
    if weather:
        temp = (weather.get("temperature") or {}).get("day")
        wind = (weather.get("wind") or {}).get("speed")
        facts.append({
            "id": "weather", "kind": "weather", "label": "天气",
            "value": f"{weather.get('description') or '—'} · {temp if temp is not None else '—'}°C",
            "detail": f"体感 {(weather.get('feels_like') or {}).get('day', '—')}°C · "
                      f"风速 {wind if wind is not None else '—'}",
            "source": "Sportmonks", "captured_at": sm_cutoff,
            "status": "confirmed", "confidence": 0.8,
        })
    referees = sm_payload.get("referees") or {}
    if referees.get("main"):
        main = referees["main"]
        facts.append({
            "id": "referee", "kind": "referee", "label": "主裁",
            "value": main.get("name") or "—",
            "detail": f"裁判组 {referees.get('crew_count') or 1} 人",
            "source": "Sportmonks", "captured_at": sm_cutoff,
            "status": "confirmed", "confidence": 0.8,
        })
    coaches = sm_payload.get("coaches") or {}
    if coaches.get("home") or coaches.get("away"):
        facts.append({
            "id": "coaches", "kind": "coach", "label": "主教练",
            "value": f"{(coaches.get('home') or {}).get('name') or '—'} / "
                     f"{(coaches.get('away') or {}).get('name') or '—'}",
            "detail": "双方主教练；只作背景", "source": "Sportmonks",
            "captured_at": sm_cutoff, "status": "confirmed", "confidence": 0.8,
        })
    highlights = (sm_payload.get("prediction_highlights") or {}).get("items") or []
    wanted = {"BTTS_PROBABILITY", "OVER_UNDER_2_5_PROBABILITY",
              "DOUBLE_CHANCE_PROBABILITY", "CORRECT_SCORE_PROBABILITY"}
    selected_highlights = [item for item in highlights if item.get("key") in wanted]
    for item in selected_highlights[:4]:
        key = item.get("key") or ""
        values = item.get("values") or {}
        if key == "BTTS_PROBABILITY":
            value = f"是 {values.get('yes', '—')}% / 否 {values.get('no', '—')}%"
        elif key == "OVER_UNDER_2_5_PROBABILITY":
            value = f"大 {values.get('yes', '—')}% / 小 {values.get('no', '—')}%"
        elif key == "DOUBLE_CHANCE_PROBABILITY":
            value = (f"主或平 {values.get('draw_home', '—')}% / "
                     f"平或客 {values.get('draw_away', '—')}% / "
                     f"主或客 {values.get('home_away', '—')}%")
        elif key == "CORRECT_SCORE_PROBABILITY":
            value = " · ".join(
                f"{row.get('score')} {row.get('probability')}%"
                for row in (item.get("scores") or [])[:3]
            )
        else:
            value = " / ".join(f"{k} {v}" for k, v in values.items() if v is not None)
        if value:
            facts.append({
                "id": f"sm_{key.lower()}", "kind": "prediction",
                "label": item.get("label") or "Sportmonks 预测",
                "value": value,
                "detail": "第三方预测参考，不参与价/市/模三闸",
                "source": "Sportmonks 预测", "captured_at": sm_cutoff,
                "status": "confirmed", "confidence": 0.7,
            })
    if v is None or not v.pick:
        unknowns.append("模型未覆盖或未给出方向")
    if not intl:
        if sm is not None and sm.odds:
            unknowns = [item for item in unknowns if item != "国际盘未覆盖"]
        else:
            unknowns.append("国际盘未覆盖")
    if sm_lineups.get("home", {}).get("starters") and sm_lineups.get("away", {}).get("starters"):
        unknowns = [item for item in unknowns if not item.startswith("首发")]
    if sm_sidelined is not None:
        unknowns = [item for item in unknowns if item != "伤停未同步"]
    if sm_standings.get("home") and sm_standings.get("away"):
        unknowns = [item for item in unknowns if item != "积分榜未同步"]
    return facts, unknowns


def _caps_and_actions(db: Session, user: User | None, v: Verdict | None,
                      match: SPMatch, now: datetime, watch: bool) -> tuple[dict, list[dict]]:
    bet = db.scalar(select(Bet).where(Bet.user_id == user.id, Bet.verdict_id == v.id)) \
        if (user and v) else None
    closed = match.kickoff <= now.strftime("%Y-%m-%d %H:%M:%S")
    settled = bool(v and v.settled)
    promoted = bool(v and v.status == "promoted")
    protection = user_streak(db, user) if user else None
    block = compliance_service.bet_block_reason(user)
    reason = block if block in ("under18", "self_excluded", "rested") else None
    can_bet = bool(user and v and promoted and not settled and not closed
                   and not bet and block is None)
    if v and promoted:
        if not user:
            reason = "login_required"
        elif settled:
            reason = "settled"
        elif closed:
            reason = "sale_closed"
        elif bet:
            reason = "already_bet"
    caps = {
        "can_bet": can_bet,
        "bet_requires_confirm": bool(protection and protection.get("active")),
        "can_watch": bool(user), "watching": watch,
        "can_why_not": bool(v and v.status != "promoted"),
        "can_view_detail": bool(v), "can_share": bool(v),
        "can_rest": bool(user),
        "can_remind_lineup": bool(user and v and not settled and not closed),
        "can_refresh": True,
    }
    actions: list[dict] = []
    if promoted:
        actions.append({"id": "bet", "enabled": can_bet, "primary": True,
                        "requires_auth": True, "reason": reason})
        actions.append({"id": "detail", "enabled": True, "primary": False,
                        "requires_auth": False, "reason": None})
    elif v:
        actions.append({"id": "why_not", "enabled": True, "primary": True,
                        "requires_auth": False, "reason": None})
        actions.append({"id": "detail", "enabled": True, "primary": False,
                        "requires_auth": False, "reason": None})
    else:
        actions.append({"id": "open_match", "enabled": True, "primary": True,
                        "requires_auth": False, "reason": None})
    if caps["can_share"]:
        actions.append({"id": "share", "enabled": True, "primary": False,
                        "requires_auth": False, "reason": None})
    if caps["can_remind_lineup"]:
        actions.append({"id": "remind_lineup", "enabled": True, "primary": False,
                        "requires_auth": True, "reason": None if user else "login_required"})
    actions.append({"id": "watch", "enabled": bool(user), "primary": False,
                    "requires_auth": True, "reason": None if user else "login_required"})
    actions.append({"id": "switch", "enabled": True, "primary": False,
                    "requires_auth": False, "reason": None})
    if user:
        actions.append({"id": "rest", "enabled": True, "primary": False,
                        "requires_auth": False, "reason": None})
    return caps, actions


def _state(match: SPMatch, v: Verdict | None, now: datetime) -> str:
    if v is not None and v.settled:
        return "settled"
    if match.kickoff <= now.strftime("%Y-%m-%d %H:%M:%S"):
        return "locked"
    if v is None:
        return "on_sale"
    return v.status if v.status in ("promoted", "screening", "killed") else "screening"


def build_pulse(db: Session, date: str | None = None) -> dict:
    now = _now()
    d = date or trade_date_now(now)
    factor = float(get_settings().pulse_display_factor)
    cache_key = f"{d}:{factor}"
    use_cache = get_settings().env != "test"
    if use_cache:
        with _PULSE_LOCK:
            cached = _PULSE_CACHE.get(cache_key)
        if cached and (time.time() - cached[0]) < _PULSE_TTL:
            return cached[1]
    matches = _matches_for_date(db, d)
    ids = [m.match_id for m in matches]
    win_start, win_end = trade_window(d)
    snapshots = [s for s in (db.scalars(
        select(SPSnapshot).where(SPSnapshot.match_id.in_(ids))).all() if ids else [])
        if _in_window(s.captured_at, d, win_start, win_end)]
    intl = [r for m in matches for r in sources_for_match(db, m)]
    sm_rows = list(db.scalars(
        select(SportmonksMatchData).where(SportmonksMatchData.match_id.in_(ids))
    ).all()) if ids else []
    ai_rows = list(db.scalars(
        select(AIResearch).where(AIResearch.match_id.in_(ids))
    ).all()) if ids else []
    sm_intel_rows = list(db.scalars(
        select(SportmonksFixtureIntel).where(SportmonksFixtureIntel.match_id.in_(ids))
    ).all()) if ids else []
    sm_ready = [r for r in sm_rows if r.probs and market_is_fresh(r)]
    ai_ready = [r for r in ai_rows if effective_status(r) == "ready"]
    sm_prediction_types = int(db.scalar(
        select(func.count(func.distinct(SportmonksPrediction.type_id)))
        .where(SportmonksPrediction.match_id.in_(ids))) or 0) if ids else 0
    model_runs = list(db.scalars(
        select(ModelRun).where(ModelRun.run_date == d, ModelRun.match_id.in_(ids))
    ).all()) if ids else []
    verdicts = list(db.scalars(select(Verdict).where(
        Verdict.trade_date == d, Verdict.match_id.in_(ids))).all()) if ids else []
    lineups = list(db.scalars(select(MatchLineup)
                              .where(MatchLineup.match_id.in_(ids))).all()) if ids else []
    injuries = list(db.scalars(select(MatchInjury)
                               .where(MatchInjury.match_id.in_(ids))).all()) if ids else []
    linked_fixtures = list(db.scalars(select(ApiFootballFixture)
                                      .where(ApiFootballFixture.match_id.in_(ids))).all()) if ids else []
    standing_rows: list[TeamStanding] = []
    for f in linked_fixtures:
        standing_rows += _standings(db, f)
    vids = [v.id for v in verdicts]
    revisions = db.scalar(select(func.count()).select_from(VerdictRevision)
                          .where(VerdictRevision.verdict_id.in_(vids))) if vids else 0
    evidence_count = sum(len((v.payload or {}).get("evidence", [])) for v in verdicts)
    lineup_sides: dict[str, set[str]] = {}
    for row in lineups:
        if row.starters and row.side in ("home", "away"):
            lineup_sides.setdefault(row.match_id, set()).add(row.side)
    lineup_ok_matches = {match_id for match_id, sides in lineup_sides.items()
                         if {"home", "away"}.issubset(sides)}
    sm_lineup_matches = 0
    sm_standings_matches = 0
    for row in sm_intel_rows:
        payload = row.payload or {}
        line = payload.get("lineups") or {}
        if ((line.get("home") or {}).get("starters")
                and (line.get("away") or {}).get("starters")):
            sm_lineup_matches += 1
            lineup_ok_matches.add(row.match_id)
        table = payload.get("standings") or {}
        if table.get("home") and table.get("away"):
            sm_standings_matches += 1
    lineup_matches = len(lineup_ok_matches)
    lineup_age = min((_age_utc(r.synced_at.isoformat(), now) for r in lineups
                      if r.synced_at is not None), default=None)
    standings_age = min((_age_utc(r.synced_at.isoformat(), now) for r in standing_rows
                         if r.synced_at is not None), default=None)
    linked_count = len({f.match_id for f in linked_fixtures if f.match_id})
    sm_intel_age = min((_age_utc(r.captured_at.isoformat(), now)
                        for r in sm_intel_rows if r.captured_at is not None),
                       default=None)
    lineup_status = ("missing" if not lineups and not sm_lineup_matches else
                     "stale" if (lineup_age is None or lineup_age > 6 * 3600)
                     and (sm_intel_age is None or sm_intel_age > 6 * 3600) else
                     "ok" if matches and lineup_matches >= len(matches) else "partial")
    standings_status = ("missing" if not standing_rows and not sm_standings_matches else
                        "stale" if (standings_age is None or standings_age > 24 * 3600)
                        and (sm_intel_age is None or sm_intel_age > 24 * 3600) else
                        "ok" if matches and (len(standing_rows) >= linked_count * 2
                                             or sm_standings_matches >= len(matches))
                        else "partial")
    model_matches = {r.match_id for r in model_runs
                     if r.gate == "model" and r.result != "pending_data"}
    model_matches |= {v.match_id for v in verdicts if _has_model(v)}
    clean = [m for m in matches if m.kickoff and m.home and m.away]
    sealed = [v for v in verdicts if v.sealed_at is not None]
    outcomes = {
        "promoted": sum(1 for v in verdicts if v.status == "promoted"),
        "screening": sum(1 for v in verdicts if v.status == "screening"),
        "killed": sum(1 for v in verdicts if v.status == "killed"),
    }
    raw_points = (len(snapshots) * 3 + len(intl) * 3 + len(model_runs)
                  + len(sm_ready) * 3 + len(ai_ready)
                  + evidence_count + len(lineups) + len(injuries)
                  + len(standing_rows) + len(sm_intel_rows) * 2)
    last_snaps = max((s.captured_at for s in snapshots), default=None)
    last_intl = max((r.retrieved_at for r in intl), default=None)
    stale = None
    for value in (last_snaps, last_intl):
        dt = _parse_cn(value)
        if dt is not None:
            stale = max(stale or 0, int((now - dt).total_seconds()))
    results_count = db.scalar(select(func.count()).select_from(MatchResult)) or 0
    all_snap = db.scalar(select(func.count()).select_from(SPSnapshot)) or 0
    all_intl = db.scalar(select(func.count()).select_from(IntlOdds)) or 0
    all_model = db.scalar(select(func.count()).select_from(ModelRun)) or 0
    all_verdicts = db.scalar(select(func.count()).select_from(Verdict)) or 0
    all_lineups = db.scalar(select(func.count()).select_from(MatchLineup)) or 0
    all_injuries = db.scalar(select(func.count()).select_from(MatchInjury)) or 0
    all_standings = db.scalar(select(func.count()).select_from(TeamStanding)) or 0
    all_points = (all_snap * 3 + all_intl * 3 + all_model + all_verdicts
                  + all_lineups + all_injuries + all_standings)
    snap_age = _age_seconds(last_snaps, now)
    intl_age = _age_seconds(last_intl, now)
    last_sm = max((r.captured_at.isoformat() for r in sm_rows
                   if r.captured_at is not None), default=None)
    last_ai = max((r.captured_at.isoformat() for r in ai_rows
                   if r.captured_at is not None), default=None)
    sm_status = ("ok" if matches and len(sm_ready) >= len(matches)
                 else "partial" if sm_ready
                 else "stale" if sm_rows else "missing")
    ai_status = ("ok" if matches and len(ai_ready) >= len(matches)
                 else "partial" if ai_ready
                 else "stale" if ai_rows else "missing")
    sources = [
        {"key": "sportmonks", "label": "Sportmonks 预测/市场",
         "status": sm_status, "last_sync": last_sm,
         "coverage": (len(sm_ready) / len(matches)) if matches else 0.0},
        {"key": "intel", "label": "AI 情报",
         "status": ai_status, "last_sync": last_ai,
         "coverage": (len(ai_ready) / len(matches)) if matches else 0.0},
        {"key": "sporttery", "label": "竞彩官方",
         "status": "ok" if snapshots and (snap_age is None or snap_age <= 35 * 60)
         else "stale" if snapshots else "missing",
         "last_sync": last_snaps, "coverage": 1.0 if snapshots else 0.0},
        {"key": "intl", "label": "国际盘（兜底）",
         "status": ("ok" if intl and len(intl) >= len(matches)
                    else "partial" if intl else "missing")
         if intl_age is None or intl_age <= 35 * 60 else "stale" if intl else "missing",
         "last_sync": last_intl,
         "coverage": min(1.0, len(intl) / len(matches)) if matches else 0.0},
        {"key": "xg", "label": "xG 模型",
         "status": "ok" if matches and len(model_matches) >= len(matches) else "partial" if model_matches else "missing",
         "last_sync": None,
         "coverage": (len(model_matches) / len(matches)) if matches else 0.0},
        {"key": "lineups", "label": "阵容/伤停",
         "status": lineup_status,
         "last_sync": max(
             [r.synced_at.isoformat() for r in lineups if r.synced_at is not None]
             + [r.captured_at.isoformat() for r in sm_intel_rows
                if r.captured_at is not None], default=None),
         "coverage": (lineup_matches / len(matches)) if matches else 0.0},
        {"key": "schedule", "label": "赛程", "status": "ok" if matches else "missing",
         "last_sync": None, "coverage": 1.0 if matches else 0.0},
        {"key": "results", "label": "赛果", "status": "ok" if results_count else "missing",
         "last_sync": None, "coverage": 1.0 if results_count else 0.0},
        {"key": "standings", "label": "积分榜",
         "status": standings_status,
         "last_sync": max(
             [r.synced_at.isoformat() for r in standing_rows
              if r.synced_at is not None]
             + [r.captured_at.isoformat() for r in sm_intel_rows
                if r.captured_at is not None], default=None),
         "coverage": (min(1.0, len(standing_rows) / (linked_count * 2))
                      if linked_count else 0.0) or (
             (sm_standings_matches / len(matches)) if matches else 0.0)},
        {"key": "sportmonks_intel", "label": "Sportmonks 阵容/积分榜/环境",
         "status": "ok" if matches and len(sm_intel_rows) >= len(matches) else
                   "partial" if sm_intel_rows else "missing",
         "last_sync": max((r.captured_at.isoformat() for r in sm_intel_rows
                           if r.captured_at is not None), default=None),
         "coverage": (len(sm_intel_rows) / len(matches)) if matches else 0.0},
    ]
    result = {
        "trade_date": d, "as_of": now.isoformat(timespec="seconds"),
        "stale_seconds": stale,
        "counts": {"matches": len(matches), "sp_snapshots": len(snapshots),
                   "intl_odds": len(intl), "model_runs": len(model_runs),
                   "verdicts": len(verdicts), "revisions": int(revisions),
                   "intel_items": evidence_count + len(lineups) + len(injuries) + len(standing_rows),
                   "sportmonks": len(sm_ready), "ai_intel": len(ai_ready),
                   "sealed_links": len(sealed), "lineups": len(lineups),
                   "injuries": len(injuries), "standings": len(standing_rows),
                   "sportmonks_intel": len(sm_intel_rows),
                   "sportmonks_lineups": sm_lineup_matches,
                   "sportmonks_standings": sm_standings_matches,
                   "sportmonks_prediction_types": sm_prediction_types},
        "data_points": raw_points,
        "display": {"data_points": int(round(raw_points * factor)), "factor": factor, "unit": "数据点"},
        "all_time": {"data_points": all_points,
                     "matches": db.scalar(select(func.count()).select_from(SPMatch)) or 0,
                     "sealed": db.scalar(select(func.count()).select_from(Verdict)
                                         .where(Verdict.sealed_at.isnot(None))) or 0},
        "stages": [
            {"key": "ingest", "label": "接入", "count": len(matches),
             "status": "ok" if matches else "missing"},
            {"key": "clean", "label": "清洗", "count": len(clean),
             "status": "ok" if clean else "missing"},
            {"key": "align", "label": "对齐", "count": len(clean),
             "status": "ok" if clean else "missing"},
            {"key": "model", "label": "模型", "count": len(model_matches),
             "status": "ok" if model_matches else "missing"},
            {"key": "gate", "label": "三闸", "count": len(verdicts),
             "status": "ok" if verdicts else "missing"},
            {"key": "seal", "label": "封存", "count": len(sealed),
             "status": "ok" if sealed else "missing"},
        ],
        "sources": sources, "outcomes": outcomes, "excluded": outcomes["killed"],
        "definition": "data_points = sp_snapshots*3 + intl_odds*3 + sm_ready*3 + ai_ready + model_runs + intel_items + sportmonks_intel*2; "
                      "display = data_points × factor；不乘场次/封存/准确率",
    }
    if use_cache:
        with _PULSE_LOCK:
            _PULSE_CACHE[cache_key] = (time.time(), result)
            if len(_PULSE_CACHE) > 200:
                for old_key in list(_PULSE_CACHE)[:100]:
                    _PULSE_CACHE.pop(old_key, None)
    return result


def build_coverage_brief(db: Session, match: SPMatch, date: str,
                         v: Verdict | None = None,
                         now: datetime | None = None) -> dict:
    """在售列表用的轻量覆盖摘要；与 focus.coverage 同一套判定，避免两处口径漂移。"""
    now = now or _now()
    v = v or _latest_verdict(db, match.match_id, date) or _latest_verdict(db, match.match_id)
    snap = _latest_snapshot(db, match.match_id)
    intl = sources_for_match(db, match)
    return _coverage(db, match, date, v, snap, intl, now)


def build_focus(db: Session, match_id: str, date: str | None = None,
                persona: str | None = None, user: User | None = None) -> dict | None:
    if date:
        trade_window(date)  # 非法日期 → ValueError → 422
    match = db.get(SPMatch, match_id)
    if match is None:
        return None
    now = _now()
    d = date or trade_date_from_kickoff(match.kickoff) or trade_date_now(now)
    v = _latest_verdict(db, match_id, date) or _latest_verdict(db, match_id)
    if v is not None:
        d = v.trade_date
    snap = _latest_snapshot(db, match_id)
    intl = sources_for_match(db, match)
    facts, unknowns = _facts(db, match, v, snap, intl, now)
    coverage = _coverage(db, match, d, v, snap, intl, now)
    sm_intel = db.get(SportmonksFixtureIntel, match_id)
    watch = bool(user and db.scalar(select(WatchTarget).where(
        WatchTarget.user_id == user.id, WatchTarget.target_type == "match",
        WatchTarget.target_id == match_id)))
    caps, actions = _caps_and_actions(db, user, v, match, now, watch)
    revisions = db.scalar(select(func.count()).select_from(VerdictRevision)
                          .where(VerdictRevision.verdict_id == v.id)) if v else 0
    persona = persona if persona in PERSONAS else (
        user.persona if user and user.persona in PERSONAS else "zhuanjia")
    result = {
        "match": {"match_id": match.match_id, "match_no": match.match_no,
                  "league": match.league, "home": match.home, "away": match.away,
                  "kickoff": match.kickoff, "sale_close": match.kickoff,
                  "single": bool(match.single_flag)},
        "verdict": _card(v) if v else None,
        "state": _state(match, v, now),
        "trade_date": d,
        "request_id": uuid.uuid4().hex,
        "as_of": now.isoformat(timespec="seconds"),
        "data_cutoff": ((v.payload or {}).get("data_cutoff") if v else None)
                       or (snap.captured_at if snap else None),
        "seal": {"hash": v.payload_hash if v else None,
                 "sealed_at": v.sealed_at.isoformat() if v and v.sealed_at else None,
                 "revision": int(revisions)},
        "coverage": coverage,
        "intel": {"facts": facts, "unknowns": unknowns,
                  "sportmonks": (sm_intel.payload or {}) if sm_intel else None},
        "interpretation": None,
        "capabilities": caps,
        "actions": actions,
        "persona": persona,
    }
    # 只读已生成的 AI 解读；聚焦接口绝不触发 LLM。
    from ..analysis.service import cached_for_focus
    result["interpretation"] = cached_for_focus(db, result)
    return result
