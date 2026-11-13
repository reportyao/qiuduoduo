"""比赛看板：即时状态、赛果、赛前预测快照与赛后对照。

数据链约定：
- 即时/赛果只读映射到竞彩的 Sportmonks fixture，不展示未映射比赛。
- 25 维战绩只认开球前锁定的 prediction snapshot，覆盖更新表不作为历史事实。
- actuals 缺失时结果固定 insufficient_data，绝不推断。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import (InteractionEvent, MatchResult, MatchResultDetail, SPMatch,
                       SPPoolSnapshot, SportmonksLiveState, SportmonksMarket,
                       SportmonksMatchData, SportmonksPrediction,
                       SportmonksPredictionSettlement,
                       SportmonksPredictionSnapshot, User, Verdict, WatchTarget,
                       utcnow)
from ...modules.sportmonks import _get
from ...modules.sportmonks_results import parse_result

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))
RULE_VERSION = "v1"
_LIVE_TTL_SECONDS = 25.0
_live_cache: dict[str, tuple[float, str]] = {}
log = logging.getLogger(__name__)


def _cn_now() -> datetime:
    return datetime.now(CN)


def _kickoff_utc(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=CN).astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _natural_day(value: str | None = None) -> str:
    return (value or _cn_now().strftime("%Y-%m-%d"))[:10]


def _score(rows: list[dict], descriptions: set[str]) -> tuple[int, int] | None:
    goals: dict[str, int] = {}
    for row in rows:
        if str(row.get("description") or "").upper() not in descriptions:
            continue
        score = row.get("score") or {}
        side = str(score.get("participant") or "").lower()
        if side in ("home", "away") and score.get("goals") is not None:
            try:
                goals[side] = int(score["goals"])
            except (TypeError, ValueError):
                return None
    if "home" in goals and "away" in goals:
        return goals["home"], goals["away"]
    return None


def _state_minute(periods: list[dict]) -> str:
    if not periods:
        return ""
    latest = max(periods, key=lambda row: int(row.get("sort_order") or 0))
    value = latest.get("minutes")
    if value is None:
        return ""
    try:
        return str(min(130, max(1, int(value))))
    except (TypeError, ValueError):
        return ""


def sync_live_states(db: Session, *, force: bool = False) -> str:
    """一次 livescores 请求覆盖全部映射场次；25 秒内复用上次结果。"""
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return "JQ_SPORTMONKS_TOKEN 未配置"
    now = time.time()
    if not force:
        cached = _live_cache.get("checked_at")
        if cached and now - cached[0] < _LIVE_TTL_SECONDS:
            return cached[1]
    base = settings.sportmonks_base_url.rstrip("/")
    payload = _get(
        base, "/livescores/inplay",
        f"api_token={token}&include=participants;scores;state;periods;league"
        "&per_page=100&locale=zh",
    )
    fixtures = {int(row.get("id") or 0): row for row in (payload or {}).get("data") or []}
    rows = [] if not fixtures else db.execute(
        select(SPMatch, SportmonksMatchData).join(
            SportmonksMatchData, SportmonksMatchData.match_id == SPMatch.match_id)
        .where(SportmonksMatchData.fixture_id.in_(list(fixtures)))
    ).all()
    updated = 0
    for match, sm in rows:
        fixture = fixtures.get(sm.fixture_id)
        if fixture is None:
            continue
        parsed = parse_result(fixture)
        current = _score(fixture.get("scores") or [], {"CURRENT"})
        ht = _score(fixture.get("scores") or [], {"HT", "1ST_HALF"})
        if current is None:
            first = _score(fixture.get("scores") or [], {"1ST_HALF"})
            second = _score(fixture.get("scores") or [], {"2ND_HALF"})
            if first and second:
                current = (first[0] + second[0], first[1] + second[1])
        state = str((fixture.get("state") or {}).get("short_name") or "").upper()
        row = db.get(SportmonksLiveState, match.match_id)
        if row is None:
            row = SportmonksLiveState(match_id=match.match_id)
            db.add(row)
        row.fixture_id = sm.fixture_id
        row.state_short = state
        row.minute = _state_minute(fixture.get("periods") or [])
        row.score_home = current[0] if current else None
        row.score_away = current[1] if current else None
        row.ht_home = ht[0] if ht else None
        row.ht_away = ht[1] if ht else None
        row.periods = fixture.get("periods") or []
        row.updated_at = utcnow()
        updated += 1
    db.commit()
    message = f"live {updated}/{len(rows)}"
    _live_cache["checked_at"] = (time.time(), message)
    return message


def _mapped_rows(db: Session, day: str) -> list[tuple[SPMatch, SportmonksMatchData]]:
    return list(db.execute(
        select(SPMatch, SportmonksMatchData).join(
            SportmonksMatchData, SportmonksMatchData.match_id == SPMatch.match_id)
        .where(SPMatch.kickoff >= f"{day} 00:00:00",
               SPMatch.kickoff <= f"{day} 23:59:59")
        .order_by(SPMatch.kickoff)
    ).all())


_INTEREST_EVENTS = ("focus_select", "verdict_viewed", "free_text_send", "intel_expand")


def _interest_ids(db: Session, user: User | None) -> set[str]:
    """关注 / 看过 / 问过：只用于静默排序，不回传任何标签。"""
    if user is None:
        return set()
    watched = set(db.scalars(
        select(WatchTarget.target_id).where(
            WatchTarget.user_id == user.id,
            WatchTarget.target_type == "match",
            WatchTarget.target_id != "")))
    interacted = set(db.scalars(
        select(InteractionEvent.match_id).where(
            InteractionEvent.user_id == user.id,
            InteractionEvent.match_id != "",
            InteractionEvent.event.in_(_INTEREST_EVENTS))))
    return {match_id for match_id in watched | interacted if match_id}


def build_live_board(db: Session, date: str | None = None, *,
                     force: bool = False) -> dict:
    """即时页：只含比赛状态，不含任何预测字段。"""
    day = _natural_day(date)
    try:
        sync_live_states(db, force=force)
    except Exception:  # noqa: BLE001 - 实时层失败不能挡住数据库旧状态
        log.exception("live state sync failed")
    states = {row.match_id: row for row in db.scalars(
        select(SportmonksLiveState).where(SportmonksLiveState.state_short.notin_(
            ["FT", "AET", "PEN", "FINISHED"])))}
    items = []
    for match, _sm in _mapped_rows(db, day):
        state = states.get(match.match_id)
        if state is None:
            continue
        items.append({
            "match_id": match.match_id,
            "match_no": match.match_no,
            "league": match.league,
            "home": match.home,
            "away": match.away,
            "kickoff": match.kickoff,
            "state": state.state_short,
            "minute": state.minute,
            "score_home": state.score_home,
            "score_away": state.score_away,
            "ht_home": state.ht_home,
            "ht_away": state.ht_away,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        })
    return {"date": day, "count": len(items), "matches": items}


def build_result_board(db: Session, date: str | None = None,
                       user: User | None = None) -> dict:
    """赛果页：只含比分与状态，不展示预测。"""
    day = _natural_day(date)
    interest_ids = _interest_ids(db, user)
    mapped = _mapped_rows(db, day)
    fixture_ids = [sm.fixture_id for _match, sm in mapped]
    results = {row.fixture_id: row for row in db.scalars(
        select(MatchResult).where(MatchResult.fixture_id.in_(fixture_ids)))} \
        if fixture_ids else {}
    live = {row.match_id: row for row in db.scalars(select(SportmonksLiveState))}
    items = []
    for match, sm in mapped:
        match_id = match.match_id
        result = results.get(sm.fixture_id)
        state = live.get(match_id)
        if result is None:
            if state and state.state_short in ("FT", "AET", "PEN", "FINISHED") \
                    and state.score_home is not None:
                items.append({
                    "match_id": match_id,
                    "match_no": match.match_no,
                    "league": match.league,
                    "home": match.home,
                    "away": match.away,
                    "kickoff": match.kickoff,
                    "status": state.state_short,
                    "score_home": state.score_home,
                    "score_away": state.score_away,
                    "ht_home": state.ht_home,
                    "ht_away": state.ht_away,
                    "source": "live_state",
                    "interest": match_id in interest_ids,
                })
            continue
        items.append({
            "match_id": match_id,
            "match_no": match.match_no,
            "league": match.league,
            "home": match.home,
            "away": match.away,
            "kickoff": match.kickoff,
            "status": result.status,
            "score_home": result.ft_home if result.ft_home is not None else result.goals_home,
            "score_away": result.ft_away if result.ft_away is not None else result.goals_away,
            "ht_home": result.ht_home,
            "ht_away": result.ht_away,
            "source": result.source,
            "interest": match_id in interest_ids,
        })
    items.sort(key=lambda item: item["kickoff"], reverse=True)
    items.sort(key=lambda item: not item["interest"])
    return {"date": day, "count": len(items), "matches": items}


def _participants(fixture: dict) -> dict[int, tuple[str, str]]:
    out = {}
    for row in fixture.get("participants") or []:
        participant_id = int(row.get("id") or 0)
        out[participant_id] = (
            str((row.get("meta") or {}).get("location") or "").lower(),
            str(row.get("name") or ""),
        )
    return out


def parse_actuals(fixture: dict) -> dict[str, Any]:
    """从 Sportmonks 赛后 fixture 提取全部对照事实。"""
    parsed = parse_result(fixture)
    if parsed is None:
        return {}
    ft_home, ft_away = parsed["ft"]
    ht = parsed["ht"] or (None, None)
    ht_home, ht_away = ht
    participants = _participants(fixture)
    corners = {"home": 0, "away": 0, "found": False}
    for row in fixture.get("statistics") or []:
        type_info = row.get("type") or {}
        if str(type_info.get("developer_name") or "").upper() != "CORNERS":
            continue
        corners["found"] = True
        side = str(row.get("location") or "").lower()
        if side in ("home", "away"):
            try:
                corners[side] += int((row.get("data") or {}).get("value") or 0)
            except (TypeError, ValueError):
                pass
    goals = [row for row in fixture.get("events") or []
             if int(row.get("type_id") or 0) == 14]
    first_side = ""
    if goals:
        goals.sort(key=lambda row: (int(row.get("minute") or 999),
                                    int(row.get("id") or 0)))
        first = goals[0]
        participant = participants.get(int(first.get("participant_id") or 0))
        if participant:
            first_side = participant[0]
    total = ft_home + ft_away

    def outcome(home: int, away: int) -> str:
        return "home" if home > away else ("draw" if home == away else "away")

    ft_outcome = outcome(ft_home, ft_away)
    ht_outcome = ""
    if ht_home is not None and ht_away is not None:
        ht_outcome = outcome(ht_home, ht_away)
    return {
        "ft_home": ft_home,
        "ft_away": ft_away,
        "ht_home": ht_home,
        "ht_away": ht_away,
        "total_goals": total,
        "btts": ft_home > 0 and ft_away > 0,
        "first_goal_side": first_side or ("draw" if total == 0 else ""),
        "ft_outcome": ft_outcome,
        "ht_outcome": ht_outcome,
        "htft": f"{ht_outcome}_{ft_outcome}" if ht_outcome else "",
        "corners_home": corners["home"] if corners["found"] else None,
        "corners_away": corners["away"] if corners["found"] else None,
        "corners_total": corners["home"] + corners["away"] if corners["found"] else None,
        "status": parsed["status"],
    }


def enrich_result_details(db: Session, days: int = 3, limit: int = 60) -> dict:
    """为已有 MatchResult 补角球/先进球/半全场；幂等，失败不阻塞赛果。"""
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置", "updated": 0}
    base = settings.sportmonks_base_url.rstrip("/")
    cutoff = (_cn_now() - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    rows = db.execute(
        select(MatchResult, SportmonksMatchData).join(
            SportmonksMatchData, SportmonksMatchData.fixture_id == MatchResult.fixture_id)
        .where(MatchResult.match_date >= cutoff)
        .order_by(MatchResult.match_date.desc()).limit(limit)
    ).all()
    updated = 0
    for result, _sm in rows:
        existing = db.get(MatchResultDetail, result.id)
        # 角球统计可能晚于 FT 才齐；已拿到角球才停止重拉，避免整场漏项。
        if existing is not None and existing.actuals:
            if existing.actuals.get("corners_total") is not None:
                continue
            captured = existing.stats_captured_at
            if captured and utcnow() - captured < timedelta(hours=6):
                continue
        payload = _get(
            base, f"/fixtures/{result.fixture_id}",
            f"api_token={token}&include=participants;scores;state;periods;"
            "statistics.type;events&locale=zh",
        )
        actuals = parse_actuals((payload or {}).get("data") or {})
        if not actuals:
            continue
        if existing is None:
            db.add(MatchResultDetail(
                result_id=result.id, fixture_id=result.fixture_id or 0,
                actuals=actuals, stats_captured_at=utcnow()))
        else:
            existing.actuals = actuals
            existing.fixture_id = result.fixture_id or 0
            existing.stats_captured_at = utcnow()
        updated += 1
    db.commit()
    return {"ok": True, "checked": len(rows), "updated": updated}


def _prediction_rows(db: Session, match_ids: list[str]) -> dict[str, list[SportmonksPrediction]]:
    out: dict[str, list[SportmonksPrediction]] = {mid: [] for mid in match_ids}
    if not match_ids:
        return out
    for row in db.scalars(select(SportmonksPrediction).where(
            SportmonksPrediction.match_id.in_(match_ids))):
        out.setdefault(row.match_id, []).append(row)
    return out


_TTG_LINES = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5)


def _implied_ou_line(selections: dict) -> str:
    """从竞彩总进球赔率反推最接近五五开的 Sportmonks 大小球盘口。

    竞彩不卖标准 O/U，只卖 0/1/2/…/7+ 总进球；用去水前的隐含概率找
    P(over) 最接近 50% 的线，避免所有比赛都固定成 2.5。
    """
    probs: dict[int, float] = {}
    for key, value in (selections or {}).items():
        text = str(key)
        if not text.startswith("s") or not text[1:].isdigit():
            continue
        try:
            odds = float(value)
        except (TypeError, ValueError):
            continue
        if odds > 1:
            probs[int(text[1:])] = 1.0 / odds
    if not probs:
        return ""
    best_line, best_gap = "", 2.0
    for line in _TTG_LINES:
        over = sum(p for goals, p in probs.items() if goals > line)
        gap = abs(over - 0.5)
        if gap < best_gap:
            best_gap, best_line = gap, f"{line:.1f}"
    return best_line


def _market_lines(db: Session, match_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not match_ids:
        return out
    sm_ou: dict[str, str] = {}
    for row in db.scalars(select(SportmonksMarket).where(
            SportmonksMarket.match_id.in_(match_ids))):
        item = out.setdefault(row.match_id, {})
        if row.market_key == "ou":
            if row.line:
                sm_ou[row.match_id] = row.line
        else:
            item[row.market_key] = row.line or ""

    # 盘口优先级：竞彩明确大小球 > 竞彩总进球隐含线 > Sportmonks 选定市场 > 2.5 兜底。
    pool_rows = list(db.scalars(select(SPPoolSnapshot).where(
        SPPoolSnapshot.match_id.in_(match_ids),
        SPPoolSnapshot.pool.in_(["ou", "ttg"]))
        .order_by(SPPoolSnapshot.captured_at)))
    sporttery_ou: dict[str, str] = {}
    ttg_line: dict[str, str] = {}
    for row in pool_rows:
        if row.pool == "ou" and row.line:
            sporttery_ou[row.match_id] = row.line
        elif row.pool == "ttg":
            line = _implied_ou_line(row.selections or {})
            if line:
                ttg_line[row.match_id] = line
    for match_id, item in out.items():
        if sporttery_ou.get(match_id):
            item["ou"] = sporttery_ou[match_id]
            item["ou_source"] = "sporttery"
        elif ttg_line.get(match_id):
            item["ou"] = ttg_line[match_id]
            item["ou_source"] = "sporttery_ttg_implied"
        elif sm_ou.get(match_id):
            item["ou"] = sm_ou[match_id]
            item["ou_source"] = "sportmonks"
        else:
            item.setdefault("ou", "2.5")
            item.setdefault("ou_source", "sportmonks")
    return out


def _product_snapshot(verdict: Verdict | None) -> tuple[dict | None, dict | None]:
    """展示用主预测取模型三方向最高概率；EV pick 保留在 product_pick。"""
    if verdict is None:
        return None, None
    payload = verdict.payload or {}
    model = payload.get("model") or {}
    shrunk = model.get("shrunk")
    probs: dict[str, float] = {}
    if isinstance(shrunk, list) and len(shrunk) >= 3:
        for key, value in zip(("home", "draw", "away"), shrunk[:3]):
            try:
                probs[key] = float(value)
            except (TypeError, ValueError):
                pass
    if len(probs) == 3:
        key = max(probs, key=probs.get)
        return {"dir": _outcome_cn(key), "prob": round(probs[key], 6)}, probs
    pick = verdict.pick or {}
    if pick.get("dir"):
        return {"dir": pick["dir"], "prob": pick.get("prob")}, None
    return None, None


def freeze_prediction_snapshots(db: Session, now: datetime | None = None) -> dict:
    """开球前持续更新、到点锁定；没有赛前数据不赛后补造。"""
    current_utc = (now or utcnow()).replace(tzinfo=None)
    cn_now = _cn_now()
    rows = db.execute(
        select(SPMatch, SportmonksMatchData).join(
            SportmonksMatchData, SportmonksMatchData.match_id == SPMatch.match_id)
        .where(SPMatch.kickoff >= (cn_now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
               SPMatch.kickoff <= (cn_now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"))
    ).all()
    ids = [match.match_id for match, _ in rows]
    predictions = _prediction_rows(db, ids)
    lines = _market_lines(db, ids)
    verdicts = {v.match_id: v for v in db.scalars(
        select(Verdict).where(Verdict.match_id.in_(ids)).order_by(Verdict.created_at))}
    opened = locked = skipped = 0
    for match, sm in rows:
        kickoff_utc = _kickoff_utc(match.kickoff)
        if kickoff_utc is None:
            skipped += 1
            continue
        existing = db.get(SportmonksPredictionSnapshot, match.match_id)
        items = predictions.get(match.match_id) or []
        if current_utc < kickoff_utc:
            if not items:
                skipped += 1
                continue
            payload = [{
                "type_id": row.type_id,
                "type_code": row.type_code,
                "type_name": row.type_name,
                "probabilities": row.probabilities or {},
                "captured_at": row.captured_at.isoformat() if row.captured_at else "",
            } for row in items]
            verdict = verdicts.get(match.match_id)
            top_pick, product_probs = _product_snapshot(verdict)
            snapshot_lines = dict(lines.get(match.match_id) or {})
            if verdict is not None:
                snapshot_lines["product_pool"] = verdict.pool
                snapshot_lines["product_line"] = verdict.goal_line or ""
            if existing is None:
                db.add(SportmonksPredictionSnapshot(
                    match_id=match.match_id, fixture_id=sm.fixture_id,
                    kickoff_cn=match.kickoff, captured_at=utcnow(),
                    predictions=payload, market_lines=snapshot_lines,
                    product_pick=verdict.pick if verdict else None,
                    product_top_pick=top_pick, product_probs=product_probs,
                    verdict_id=verdict.id if verdict else None, status="open"))
            elif existing.locked_at is None:
                existing.predictions = payload
                existing.captured_at = utcnow()
                existing.market_lines = snapshot_lines or existing.market_lines
                existing.product_pick = verdict.pick if verdict else existing.product_pick
                existing.product_top_pick = top_pick or existing.product_top_pick
                existing.product_probs = product_probs or existing.product_probs
                existing.verdict_id = verdict.id if verdict else existing.verdict_id
            opened += 1
            continue
        if existing is not None:
            if existing.locked_at is None:
                existing.locked_at = utcnow()
                existing.status = "locked"
                locked += 1
            continue
        if items and all(row.captured_at and row.captured_at <= kickoff_utc for row in items):
            verdict = verdicts.get(match.match_id)
            top_pick, product_probs = _product_snapshot(verdict)
            db.add(SportmonksPredictionSnapshot(
                match_id=match.match_id, fixture_id=sm.fixture_id,
                kickoff_cn=match.kickoff,
                captured_at=max(row.captured_at for row in items),
                locked_at=utcnow(), cutoff_reason="legacy_cache",
                predictions=[{
                    "type_id": row.type_id,
                    "type_code": row.type_code,
                    "type_name": row.type_name,
                    "probabilities": row.probabilities or {},
                    "captured_at": row.captured_at.isoformat() if row.captured_at else "",
                } for row in items],
                market_lines={
                    **(lines.get(match.match_id) or {}),
                    "product_pool": verdict.pool if verdict else "",
                    "product_line": verdict.goal_line if verdict else "",
                },
                product_pick=verdict.pick if verdict else None,
                product_top_pick=top_pick, product_probs=product_probs,
                verdict_id=verdict.id if verdict else None,
                snapshot_source="legacy_cache", status="locked"))
            locked += 1
        else:
            skipped += 1
    db.commit()
    return {"ok": True, "opened": opened, "locked": locked, "skipped": skipped}


def _argmax(values: dict[str, Any]) -> tuple[str, float | None]:
    best_key, best_value = "", None
    for key, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if best_value is None or number > best_value:
            best_key, best_value = str(key), number
    return best_key, best_value


def _probabilities(item: dict) -> dict[str, Any]:
    """正确比分在 Sportmonks 里嵌了一层 scores，其余维度是平铺的。"""
    values = item.get("probabilities") or {}
    nested = values.get("scores") if isinstance(values, dict) else None
    return nested if isinstance(nested, dict) and nested else values


def _norm_prob(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value / 100.0, 6) if value > 1.5 else round(value, 6)


def _outcome_cn(key: str) -> str:
    return {"home": "主胜", "draw": "平局", "away": "客胜"}.get(key, key)


def _line_text(code: str, prefix: str, fallback: str = "") -> str:
    line = _code_line(code, prefix)
    if line is None:
        return fallback
    return str(int(line)) if line.is_integer() else str(line)


def _predicted_label(code: str, key: str, market_line: str = "") -> str:
    """把 argmax 的英文键翻成用户可读的预测方向。"""
    if not key:
        return ""
    outcome = {"home": "主胜", "draw": "平局", "away": "客胜"}
    if code in ("FULLTIME_RESULT_PROBABILITY", "FIRST_HALF_WINNER_PROBABILITY",
                "product_main"):
        return outcome.get(key, key)
    if code == "BTTS_PROBABILITY":
        return {"yes": "是", "no": "否"}.get(key, key)
    if code == "TEAM_TO_SCORE_FIRST_PROBABILITY":
        return {"home": "主队先进球", "away": "客队先进球",
                "draw": "双方无进球"}.get(key, key)
    if code == "DOUBLE_CHANCE_PROBABILITY":
        return {"draw_home": "主或平", "draw_away": "平或客",
                "home_away": "主或客"}.get(key, key)
    if code == "HTFT_PROBABILITY":
        parts = key.split("_")
        if len(parts) == 2:
            return f"{outcome.get(parts[0], parts[0])}/{outcome.get(parts[1], parts[1])}"
        return key
    if code == "CORRECT_SCORE_PROBABILITY":
        if key.startswith("Other_"):
            return f"其他比分 {key[6:]}"
        return key
    if code.startswith("CORNERS_OVER_UNDER_"):
        label = {"over": "大", "under": "小", "equal": "走水"}.get(key, key)
        return f"{label} {_line_text(code, 'CORNERS_OVER_UNDER_')}".strip()
    if code.startswith("HOME_OVER_UNDER_") or code.startswith("AWAY_OVER_UNDER_"):
        prefix = "主队" if code.startswith("HOME_") else "客队"
        label = {"yes": "大", "no": "小"}.get(key, key)
        line = _line_text(code, "HOME_OVER_UNDER_" if code.startswith("HOME_")
                          else "AWAY_OVER_UNDER_")
        return f"{prefix}{label} {line}".strip()
    if code.startswith("OVER_UNDER_"):
        label = {"yes": "大", "no": "小"}.get(key, key)
        return f"{label} {market_line or _line_text(code, 'OVER_UNDER_')}".strip()
    return key


def _code_line(code: str, prefix: str) -> float | None:
    """从 `OVER_UNDER_2_5_PROBABILITY` 这类代码中解析盘口线。"""
    core = code[len(prefix):]
    if core.endswith("_PROBABILITY"):
        core = core[:-len("_PROBABILITY")]
    try:
        return float(core.replace("_", "."))
    except (TypeError, ValueError):
        return None


def _actual_for_type(code: str, actuals: dict[str, Any]) -> tuple[str, str]:
    total = actuals.get("total_goals")
    ft = actuals.get("ft_outcome")
    if code == "FULLTIME_RESULT_PROBABILITY":
        return str(ft or ""), _outcome_cn(str(ft or ""))
    if code == "BTTS_PROBABILITY":
        value = actuals.get("btts")
        if value is None:
            return "", ""
        return ("yes" if value else "no"), ("是" if value else "否")
    if code == "FIRST_HALF_WINNER_PROBABILITY":
        key = str(actuals.get("ht_outcome") or "")
        return key, _outcome_cn(key)
    if code == "TEAM_TO_SCORE_FIRST_PROBABILITY":
        key = str(actuals.get("first_goal_side") or "")
        return key, {"home": "主队", "away": "客队", "draw": "无进球"}.get(key, key)
    if code == "DOUBLE_CHANCE_PROBABILITY":
        if not ft:
            return "", ""
        key = {"home": "draw_home", "draw": "draw_away", "away": "home_away"}[str(ft)]
        return key, {"draw_home": "主或平", "draw_away": "平或客", "home_away": "主或客"}[key]
    if code == "HTFT_PROBABILITY":
        key = str(actuals.get("htft") or "")
        return key, _predicted_label(code, key)
    if code == "CORRECT_SCORE_PROBABILITY":
        score = f"{actuals.get('ft_home')}-{actuals.get('ft_away')}"
        return score, score
    if code.startswith("CORNERS_OVER_UNDER_"):
        corners = actuals.get("corners_total")
        line = _code_line(code, "CORNERS_OVER_UNDER_")
        if corners is None or line is None:
            return "", ""
        key = "over" if corners > line else ("equal" if corners == line else "under")
        return key, {"over": "大", "under": "小", "equal": "走水"}[key]
    if code.startswith("HOME_OVER_UNDER_") or code.startswith("AWAY_OVER_UNDER_"):
        prefix = "home" if code.startswith("HOME_") else "away"
        goals = actuals.get(f"ft_{prefix}")
        line = _code_line(code, "HOME_OVER_UNDER_" if prefix == "home"
                          else "AWAY_OVER_UNDER_")
        if goals is None or line is None:
            return "", ""
        return ("yes" if goals > line else "no"), ("大" if goals > line else "小")
    if code.startswith("OVER_UNDER_"):
        line = _code_line(code, "OVER_UNDER_")
        if total is None or line is None:
            return "", ""
        return ("yes" if total > line else "no"), ("大" if total > line else "小")
    return "", ""


def _product_actual(snapshot: SportmonksPredictionSnapshot,
                    actuals: dict[str, Any], direction: str) -> tuple[str, str]:
    if direction not in ("主胜", "平局", "客胜"):
        return "", ""
    ft_home = actuals.get("ft_home")
    ft_away = actuals.get("ft_away")
    if ft_home is None or ft_away is None:
        return "", ""
    actual_key = str(actuals.get("ft_outcome") or "")
    lines = snapshot.market_lines or {}
    handicap = str(lines.get("product_pool") or lines.get("pool") or "") == "hhad"
    if handicap:
        try:
            line = float(lines.get("product_line") or 0)
        except (TypeError, ValueError):
            line = 0.0
        diff = int(ft_home) - int(ft_away) + line
        actual_key = "home" if diff > 0 else ("draw" if diff == 0 else "away")
    if not actual_key:
        return "", ""
    if handicap:
        return actual_key, {"home": "让球主胜", "draw": "让球平",
                            "away": "让球客胜"}[actual_key]
    return actual_key, _outcome_cn(actual_key)


def _new_settlement(snapshot: SportmonksPredictionSnapshot, *, source: str,
                    prediction_type: str, label: str, predicted_key: str,
                    predicted_label: str,
                    probability: float | None, market_line: str,
                    actual_key: str, actual_label: str, counted: bool
                    ) -> SportmonksPredictionSettlement:
    if not actual_key:
        result = "insufficient_data"
    elif predicted_key == actual_key:
        result = "hit"
    elif actual_key == "equal":
        result = "push"
    else:
        result = "miss"
    return SportmonksPredictionSettlement(
        match_id=snapshot.match_id, fixture_id=snapshot.fixture_id,
        kickoff_cn=snapshot.kickoff_cn, source=source,
        prediction_type=prediction_type, prediction_label=label,
        predicted_key=predicted_key, predicted_label=predicted_label,
        predicted_probability=_norm_prob(probability),
        market_line=market_line, actual_key=actual_key, actual_label=actual_label,
        result=result, counted_in_accuracy=counted, rule_version=RULE_VERSION)


def settle_prediction_snapshots(db: Session, limit: int = 100) -> dict:
    """按锁定快照 + 赛果 actuals 生成/刷新对照行；幂等。"""
    snapshots = db.scalars(
        select(SportmonksPredictionSnapshot)
        .where(SportmonksPredictionSnapshot.locked_at.isnot(None))
        .order_by(SportmonksPredictionSnapshot.kickoff_cn.desc()).limit(limit)).all()
    details = {row.fixture_id: row for row in db.scalars(select(MatchResultDetail))}
    settled = skipped = 0
    for snapshot in snapshots:
        detail = details.get(snapshot.fixture_id)
        if detail is None or not detail.actuals:
            skipped += 1
            continue
        actuals = detail.actuals
        existing_sportmonks = {row.prediction_type: row for row in db.scalars(
            select(SportmonksPredictionSettlement).where(
                SportmonksPredictionSettlement.match_id == snapshot.match_id,
                SportmonksPredictionSettlement.source == "sportmonks"))}
        existing_product = db.scalar(select(SportmonksPredictionSettlement).where(
            SportmonksPredictionSettlement.match_id == snapshot.match_id,
            SportmonksPredictionSettlement.source == "product"))
        rows: list[SportmonksPredictionSettlement] = []
        top_pick = snapshot.product_top_pick or {}
        if not top_pick and snapshot.verdict_id:
            top_pick, _ = _product_snapshot(db.get(Verdict, snapshot.verdict_id))
        if not top_pick:
            top_pick = snapshot.product_pick or {}
        direction = str(top_pick.get("dir") or "")
        if direction:
            actual_key, actual_label = _product_actual(snapshot, actuals, direction)
            prob = top_pick.get("prob")
            product_pool = str((snapshot.market_lines or {}).get("product_pool") or "")
            product_prefix = "让球" if product_pool == "hhad" else ""
            rows.append(_new_settlement(
                snapshot, source="product", prediction_type="product_main",
                label="主预测",
                predicted_key={"主胜": "home", "平局": "draw", "客胜": "away"}.get(
                    direction, direction),
                predicted_label=f"{product_prefix}{direction}",
                probability=float(prob) if prob is not None else None,
                market_line=str((snapshot.market_lines or {}).get("product_line") or ""),
                actual_key=actual_key, actual_label=actual_label, counted=True))
        selected_ou = str((snapshot.market_lines or {}).get("ou") or "2.5")
        available_codes = {str(x.get("type_code") or "") for x in snapshot.predictions or []}
        ou_code = "OVER_UNDER_" + selected_ou.replace(".", "_") + "_PROBABILITY"
        if ou_code not in available_codes:
            # 竞彩推出来的线（如 0.5）Sportmonks 未必提供；取最接近的可用盘口。
            try:
                target = float(selected_ou)
            except (TypeError, ValueError):
                target = 2.5
            options = []
            for candidate in available_codes:
                if not candidate.startswith("OVER_UNDER_"):
                    continue
                line = _code_line(candidate, "OVER_UNDER_")
                if line is not None:
                    options.append((abs(line - target), candidate, line))
            if options:
                _, ou_code, line = min(options)
                selected_ou = str(int(line)) if line.is_integer() else str(line)
        has_product = bool(direction)
        for item in snapshot.predictions or []:
            code = str(item.get("type_code") or "")
            probabilities = _probabilities(item)
            if code == "CORRECT_SCORE_PROBABILITY":
                # Other_1/Other_2/Other_X 是聚合桶，不能当成一个具体比分。
                probabilities = {key: value for key, value in probabilities.items()
                                 if not str(key).startswith("Other_")}
            predicted_key, probability = _argmax(probabilities)
            # 角球大小球预测键是 yes/no/equal，实际值统一为 over/under/equal。
            if code.startswith("CORNERS_OVER_UNDER_"):
                predicted_key = {"yes": "over", "no": "under"}.get(
                    predicted_key, predicted_key)
            actual_key, actual_label = _actual_for_type(code, actuals)
            counted = False
            if code == "FULLTIME_RESULT_PROBABILITY" and not has_product:
                counted = True
            if code == ou_code:
                counted = True
            if code == "BTTS_PROBABILITY":
                counted = True
            rows.append(_new_settlement(
                snapshot, source="sportmonks", prediction_type=code,
                label=str(item.get("type_name") or code), predicted_key=predicted_key,
                predicted_label=_predicted_label(
                    code, predicted_key,
                    selected_ou if code.startswith("OVER_UNDER_") else ""),
                probability=probability,
                market_line=selected_ou if code.startswith("OVER_UNDER_") else "",
                actual_key=actual_key, actual_label=actual_label, counted=counted))
        for row in rows:
            old = existing_product if row.source == "product" else existing_sportmonks.get(row.prediction_type)
            if old is None:
                db.add(row)
            else:
                for field in ("fixture_id", "kickoff_cn", "prediction_label",
                              "predicted_key", "predicted_label",
                              "predicted_probability", "market_line",
                              "actual_key", "actual_label", "result",
                              "counted_in_accuracy", "rule_version"):
                    setattr(old, field, getattr(row, field))
                old.settled_at = utcnow()
        settled += 1
    db.commit()
    return {"ok": True, "settled": settled, "skipped": skipped}


def _accuracy(rows: list[SportmonksPredictionSettlement]) -> dict[str, Any]:
    counted = [row for row in rows if row.counted_in_accuracy]
    settled = [row for row in counted if row.result in ("hit", "miss", "push")]
    hits = sum(1 for row in settled if row.result == "hit")
    pushes = sum(1 for row in settled if row.result == "push")
    return {
        "total_items": len(counted),
        "settled_items": len(settled),
        "hit_items": hits,
        "push_items": pushes,
        "miss_items": len(settled) - hits - pushes,
        "hit_rate": round(hits / len(settled), 6) if settled else None,
    }


def build_prediction_history(db: Session, date: str | None = None,
                             user: User | None = None) -> dict:
    """预测战绩列表：汇总 + 每场主结果；25 维详情另走单场接口。"""
    day = _natural_day(date)
    interest_ids = _interest_ids(db, user)
    rows = db.scalars(
        select(SportmonksPredictionSettlement)
        .where(SportmonksPredictionSettlement.kickoff_cn.like(f"{day}%"))
        .order_by(SportmonksPredictionSettlement.kickoff_cn.desc())).all()
    by_match: dict[str, list[SportmonksPredictionSettlement]] = {}
    for row in rows:
        by_match.setdefault(row.match_id, []).append(row)
    match_rows = {row.match_id: row for row in db.scalars(
        select(SPMatch).where(SPMatch.match_id.in_(list(by_match))))}
    snapshots = {row.match_id: row for row in db.scalars(
        select(SportmonksPredictionSnapshot).where(
            SportmonksPredictionSnapshot.match_id.in_(list(by_match))))}
    fixture_ids = [row.fixture_id for row in snapshots.values()]
    results = {row.fixture_id: row for row in db.scalars(
        select(MatchResult).where(MatchResult.fixture_id.in_(fixture_ids)))} \
        if fixture_ids else {}
    items = []
    for mid, entries in by_match.items():
        match = match_rows.get(mid)
        if match is None:
            continue
        snapshot = snapshots.get(mid)
        result = results.get(snapshot.fixture_id) if snapshot else None
        main = next((row for row in entries if row.source == "product"), None)
        if main is None:
            main = next((row for row in entries
                         if row.prediction_type == "FULLTIME_RESULT_PROBABILITY"), None)
        items.append({
            "match_id": mid,
            "match_no": match.match_no,
            "league": match.league,
            "home": match.home,
            "away": match.away,
            "kickoff": match.kickoff,
            "score_home": (result.ft_home if result and result.ft_home is not None
                           else result.goals_home if result else None),
            "score_away": (result.ft_away if result and result.ft_away is not None
                           else result.goals_away if result else None),
            "status": result.status if result else "",
            "interest": mid in interest_ids,
            "main_prediction": {
                "label": main.prediction_label,
                "key": main.predicted_key,
                "direction": main.predicted_label,
                "probability": main.predicted_probability,
                "actual": main.actual_label,
                "result": main.result,
            } if main else None,
            "settled_dimensions": sum(
                1 for row in entries if row.result in ("hit", "miss", "push")),
            "total_dimensions": len(entries),
        })
    items.sort(key=lambda item: item["kickoff"], reverse=True)
    items.sort(key=lambda item: not item["interest"])
    return {"date": day, "summary": _accuracy(rows), "count": len(items), "matches": items}


def _probability_rows(snapshot: SportmonksPredictionSnapshot | None,
                      row: SportmonksPredictionSettlement,
                      raw_item: dict | None,
                      product_probs: dict | None) -> list[dict]:
    if row.source == "product":
        source = dict(product_probs or {})
        pool = str((snapshot.market_lines or {}).get("product_pool") or "") if snapshot else ""
        if pool == "hhad":
            labels = {"home": "让球主胜", "draw": "让球平", "away": "让球客胜"}
        else:
            labels = {key: _outcome_cn(key) for key in source}
    else:
        source = _probabilities(raw_item or {})
        labels = {str(key): _predicted_label(row.prediction_type, str(key), row.market_line)
                  for key in source}
    out = []
    for key, value in source.items():
        try:
            probability = float(value)
        except (TypeError, ValueError):
            continue
        # Sportmonks 原始预测全是百分数（0.06 也是 0.06%），不能套 0-1 启发式。
        probability = probability if row.source == "product" else probability / 100.0
        if probability < 0:
            continue
        out.append({"key": str(key), "label": labels.get(str(key), str(key)),
                    "probability": round(probability, 6)})
    out.sort(key=lambda item: item["probability"], reverse=True)
    return out


def build_prediction_history_detail(db: Session, match_id: str) -> dict | None:
    match = db.get(SPMatch, match_id)
    if match is None:
        return None
    snapshot = db.get(SportmonksPredictionSnapshot, match_id)
    result = db.scalar(select(MatchResult).where(
        MatchResult.fixture_id == snapshot.fixture_id)) if snapshot else None
    rows = db.scalars(select(SportmonksPredictionSettlement).where(
        SportmonksPredictionSettlement.match_id == match_id)).all()
    product_probs: dict = {}
    if snapshot is not None:
        product_probs = dict(snapshot.product_probs or {})
        if not product_probs and snapshot.verdict_id:
            _, product_probs = _product_snapshot(db.get(Verdict, snapshot.verdict_id))
    raw_items = {str(item.get("type_code") or ""): item
                 for item in (snapshot.predictions or [])} if snapshot else {}
    return {
        "match_id": match_id,
        "match_no": match.match_no,
        "league": match.league,
        "home": match.home,
        "away": match.away,
        "kickoff": match.kickoff,
        "score_home": (result.ft_home if result and result.ft_home is not None
                       else result.goals_home if result else None),
        "score_away": (result.ft_away if result and result.ft_away is not None
                       else result.goals_away if result else None),
        "status": result.status if result else "",
        "snapshot": {
            "captured_at": snapshot.captured_at.isoformat() if snapshot and snapshot.captured_at else None,
            "locked_at": snapshot.locked_at.isoformat() if snapshot and snapshot.locked_at else None,
            "status": snapshot.status if snapshot else "missing",
            "source": snapshot.snapshot_source if snapshot else "",
        },
        "summary": _accuracy(rows),
        "items": [{
            "source": row.source,
            "type": row.prediction_type,
            "label": row.prediction_label,
            "predicted_key": row.predicted_key,
            "predicted_label": row.predicted_label,
            "predicted_probability": row.predicted_probability,
            "probabilities": _probability_rows(
                snapshot, row, raw_items.get(row.prediction_type), product_probs),
            "market_line": row.market_line,
            "actual_key": row.actual_key,
            "actual_label": row.actual_label,
            "result": row.result,
            "counted_in_accuracy": row.counted_in_accuracy,
        } for row in rows],
    }
