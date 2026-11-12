"""Sportmonks 赛果回填：把已完赛场次的比分写入 match_results，再结算判决。

为什么需要它：football-data.co.uk 只覆盖五大联赛，竞彩大量场次（英锦标赛、
日联赛杯等）永远等不到赛果，公开账本和模型评估会一直是空的。Sportmonks 已经
保存了每场的 fixture_id，直接按 fixture 取 CURRENT 比分即可覆盖全部已映射场次。

只处理已完赛（FT/AET/PEN）且开球在最近 N 天的场次；拿不到比分就保持未结算，
绝不推算。
"""
from __future__ import annotations

import logging
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
log = logging.getLogger(__name__)
_SCORE_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")


def _goals_from_rows(rows: list[dict], descriptions: set[str]) -> tuple[int, int] | None:
    picked = [row for row in rows
              if str(row.get("description") or "").upper() in descriptions]
    goals: dict[str, int] = {}
    for row in picked:
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


def parse_result(fixture: dict) -> dict | None:
    """解析 FT90 / HT / 状态。

    CURRENT 在 AET/PEN 后可能含加时点球比分，不能用于 1X2。
    AET/PEN 必须找到明确的 FT 行才返回；没有就保持未结算。
    """
    state = str((fixture.get("state") or {}).get("short_name") or "").upper()
    if state not in _FINISHED:
        return None
    rows = fixture.get("scores") or []
    ft = _goals_from_rows(rows, {"FT", "2ND_HALF"})
    if ft is None and state in ("FT", "FINISHED"):
        ft = _goals_from_rows(rows, {"CURRENT"})
    if ft is None and state in ("FT", "FINISHED"):
        match = _SCORE_RE.search(str(fixture.get("result_info") or ""))
        if match:
            ft = (int(match.group(1)), int(match.group(2)))
    if ft is None:
        return None
    ht = _goals_from_rows(rows, {"HT", "1ST_HALF"})
    return {"ft": ft, "ht": ht, "status": "FT" if state == "FINISHED" else state}


def parse_score(fixture: dict) -> tuple[int, int] | None:
    """兼容旧调用：只返回 FT90。"""
    parsed = parse_result(fixture)
    return parsed["ft"] if parsed else None


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
        parsed = parse_result(fixture)
        if parsed is None:
            skipped += 1
            continue
        score, ht = parsed["ft"], parsed["ht"]
        db.add(MatchResult(
            source="sportmonks", league=match.league,
            home_raw=sm.home_name, away_raw=sm.away_name,
            home=match.home, away=match.away, match_date=match_date,
            fixture_id=sm.fixture_id, status=parsed["status"],
            ft_home=score[0], ft_away=score[1],
            ht_home=ht[0] if ht else None, ht_away=ht[1] if ht else None,
            goals_home=score[0], goals_away=score[1],
            retrieved_at=utcnow().isoformat(),
        ))
        seen.add(key)
        inserted += 1
        # 赛后情报是增强项：失败不影响赛果落库/结算。
        try:
            from .sportmonks_intel import sync_postmatch_intel
            sync_postmatch_intel(db, base, token, match, sm.fixture_id)
        except Exception:  # noqa: BLE001
            log.exception("sportmonks postmatch intel failed match_id=%s",
                          match.match_id)
    db.commit()
    from .settlement import settle_pending
    from .plan_service import settle_open_cycles
    settled = settle_pending(db)
    settle_open_cycles(db)
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
            parsed = parse_result(fixture)
            if parsed is None:
                continue
            score, ht = parsed["ft"], parsed["ht"]
            participants = {p.get("meta", {}).get("location"): p.get("name", "")
                            for p in fixture.get("participants") or []}
            db.add(MatchResult(
                source="sportmonks-backfill", league=verdict.league,
                home_raw=participants.get("home", ""),
                away_raw=participants.get("away", ""),
                home=verdict.home, away=verdict.away, match_date=day,
                fixture_id=fixture.get("id"), status=parsed["status"],
                ft_home=score[0], ft_away=score[1],
                ht_home=ht[0] if ht else None, ht_away=ht[1] if ht else None,
                goals_home=score[0], goals_away=score[1],
                retrieved_at=utcnow().isoformat(),
            ))
            existing.add(key)
            inserted += 1
    db.commit()
    from .settlement import settle_pending
    from .plan_service import settle_open_cycles
    settled = settle_pending(db)
    settle_open_cycles(db)
    return {"ok": True, "checked": checked, "inserted": inserted,
            "settled": settled, "days": days}
