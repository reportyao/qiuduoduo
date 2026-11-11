"""Sportmonks 赛果回填：把已完赛场次的比分写入 match_results，再结算判决。

为什么需要它：football-data.co.uk 只覆盖五大联赛，竞彩大量场次（英锦标赛、
日联赛杯等）永远等不到赛果，公开账本和模型评估会一直是空的。Sportmonks 已经
保存了每场的 fixture_id，直接按 fixture 取 CURRENT 比分即可覆盖全部已映射场次。

只处理已完赛（FT/AET/PEN）且开球在最近 N 天的场次；拿不到比分就保持未结算，
绝不推算。
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import MatchResult, SPMatch, SportmonksMatchData, Verdict, utcnow
from .sportmonks import _get, match_fixture

CN = timezone(timedelta(hours=8))
_FINISHED = {"FT", "AET", "PEN", "FINISHED"}
_SCORE_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")


def parse_score(fixture: dict) -> tuple[int, int] | None:
    """从 fixture.scores / result_info 取主客进球；只接受已完赛状态。"""
    state = str((fixture.get("state") or {}).get("short_name") or "").upper()
    if state not in _FINISHED:
        return None
    rows = [row for row in fixture.get("scores") or []
            if str(row.get("description") or "").upper() == "CURRENT"]
    if not rows:
        rows = [row for row in fixture.get("scores") or []
                if row.get("type_id") == 1525]
    goals: dict[str, int] = {}
    for row in rows:
        score = row.get("score") or {}
        side = str(score.get("participant") or "").lower()
        if side in ("home", "away") and score.get("goals") is not None:
            try:
                goals[side] = int(score["goals"])
            except (TypeError, ValueError):
                return None
    if "home" in goals and "away" in goals:
        return goals["home"], goals["away"]
    match = _SCORE_RE.search(str(fixture.get("result_info") or ""))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def sync_results(db: Session, days: int = 2, limit: int = 80) -> dict:
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置",
                "checked": 0, "inserted": 0}
    base = settings.sportmonks_base_url.rstrip("/")
    now = datetime.now(CN)
    start = (now - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")
    end = (now - timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.execute(
        select(SportmonksMatchData, SPMatch).join(
            SPMatch, SPMatch.match_id == SportmonksMatchData.match_id)
        .where(SPMatch.kickoff >= start, SPMatch.kickoff <= end)
        .order_by(SPMatch.kickoff.desc()).limit(limit)
    ).all()
    inserted = 0
    skipped = 0
    seen: set[tuple[str, str, str]] = set()
    for sm, match in rows:
        match_date = match.kickoff[:10]
        key = (match.home, match.away, match_date)
        if key in seen:
            skipped += 1
            continue
        exists = db.scalar(select(MatchResult).where(
            MatchResult.home == match.home, MatchResult.away == match.away,
            MatchResult.match_date == match_date))
        if exists is not None:
            seen.add(key)
            skipped += 1
            continue
        payload = _get(base, f"/fixtures/{sm.fixture_id}",
                       f"api_token={token}&include=participants;scores;state;league&locale=zh")
        time.sleep(0.15)
        fixture = (payload or {}).get("data") or {}
        score = parse_score(fixture)
        if score is None:
            skipped += 1
            continue
        db.add(MatchResult(
            source="sportmonks", league=match.league,
            home_raw=sm.home_name, away_raw=sm.away_name,
            home=match.home, away=match.away, match_date=match_date,
            goals_home=score[0], goals_away=score[1],
            retrieved_at=utcnow().isoformat(),
        ))
        seen.add(key)
        inserted += 1
    db.commit()
    settled = 0
    if inserted:
        from .settle import settle_verdicts
        settled = settle_verdicts(db)
    return {"ok": True, "checked": len(rows), "inserted": inserted,
            "skipped": skipped, "settled": settled}


def _fetch_day(base: str, token: str, day: str) -> list[dict]:
    d = datetime.strptime(day, "%Y-%m-%d")
    start = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    end = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    out: list[dict] = []
    for page in range(1, 4):
        payload = _get(
            base, f"/fixtures/between/{start}/{end}",
            f"api_token={token}&include=participants;scores;state;league"
            f"&per_page=50&page={page}&locale=zh")
        rows = (payload or {}).get("data") or []
        out.extend(rows)
        time.sleep(0.15)
        if len(rows) < 50:
            break
    return out


def backfill_verdict_results(db: Session, days: int = 14) -> dict:
    """给历史未结算判决回填赛果：按开球日拉 Sportmonks fixtures，逐场保守匹配。

    只用于账号早期的数据补齐；每天最多 3 页 fixture，按日期复用，不做逐场请求。
    """
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置",
                "inserted": 0, "settled": 0}
    base = settings.sportmonks_base_url.rstrip("/")
    cutoff = (datetime.now(CN) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    verdicts = db.scalars(select(Verdict).where(
        Verdict.trade_date >= cutoff, Verdict.pick.isnot(None),
        Verdict.settled.is_(None))).all()
    by_day: dict[str, list[Verdict]] = {}
    for verdict in verdicts:
        by_day.setdefault(verdict.kickoff[:10], []).append(verdict)
    existing = {
        (home, away, day)
        for home, away, day in db.execute(
            select(MatchResult.home, MatchResult.away, MatchResult.match_date)
            .where(MatchResult.match_date.in_(list(by_day)))).all()
    } if by_day else set()
    inserted = 0
    checked = len(verdicts)
    for day, items in sorted(by_day.items()):
        fixtures = _fetch_day(base, token, day)
        if not fixtures:
            continue
        for verdict in items:
            key = (verdict.home, verdict.away, day)
            if key in existing:
                continue
            proxy = SimpleNamespace(
                home=verdict.home, away=verdict.away, kickoff=verdict.kickoff,
                match_id=verdict.match_id, match_no=verdict.match_no)
            fixture = match_fixture(proxy, fixtures)
            if fixture is None:
                continue
            score = parse_score(fixture)
            if score is None:
                continue
            participants = {p.get("meta", {}).get("location"): p.get("name", "")
                            for p in fixture.get("participants") or []}
            db.add(MatchResult(
                source="sportmonks-backfill", league=verdict.league,
                home_raw=participants.get("home", ""),
                away_raw=participants.get("away", ""),
                home=verdict.home, away=verdict.away, match_date=day,
                goals_home=score[0], goals_away=score[1],
                retrieved_at=utcnow().isoformat(),
            ))
            existing.add(key)
            inserted += 1
    db.commit()
    settled = 0
    if inserted:
        from .settle import settle_verdicts
        settled = settle_verdicts(db)
    return {"ok": True, "checked": checked, "inserted": inserted,
            "settled": settled, "days": days}
