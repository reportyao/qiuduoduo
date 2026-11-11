"""Sportmonks 同步：按竞彩销售日拉 1X2 预测与市场 1X2，挂到 match_id。

设计约束：
- 只做增强，不创建竞彩场次；映射不上就跳过，绝不猜。
- 预测/赔率任一缺失也可以落库（另一项照常展示）。
- 所有请求带 locale=zh；中文名仅用于展示，映射仍按开球时间 + 名称相似度。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import SPMatch, SportmonksMatchData, utcnow
from .timeutil import trade_window

CN_TZ = timezone(timedelta(hours=8))


def _norm(name: str) -> str:
    value = (name or "").lower()
    value = re.sub(r"[\s\-_.·,，。()（）]", "", value)
    for suffix in ("足球俱乐部", "俱乐部", "足球会", "队", "fc"):
        value = value.replace(suffix, "")
    return value


def _similar(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def _kickoff_utc(match: SPMatch) -> datetime | None:
    try:
        return datetime.strptime(match.kickoff, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=CN_TZ).astimezone(timezone.utc)
    except ValueError:
        return None


def _fixture_kickoff(fixture: dict) -> datetime | None:
    try:
        return datetime.strptime(fixture.get("starting_at", ""), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def match_fixture(match: SPMatch, fixtures: list[dict]) -> dict | None:
    """开球时间 ±2h 内，一队精确 + 另一队相似，或两队都高相似，才接受。"""
    kickoff = _kickoff_utc(match)
    if kickoff is None:
        return None
    best: tuple[float, dict] | None = None
    for fixture in fixtures:
        fk = _fixture_kickoff(fixture)
        if fk is None or abs((fk - kickoff).total_seconds()) > 2 * 3600:
            continue
        parts = {p.get("meta", {}).get("location"): p.get("name", "")
                 for p in fixture.get("participants") or []}
        hs = _similar(match.home, parts.get("home", ""))
        as_ = _similar(match.away, parts.get("away", ""))
        exact = hs == 1.0 or as_ == 1.0
        score = hs + as_
        if exact and min(hs, as_) >= 0.6:
            candidate = (score, fixture)
        elif min(hs, as_) >= 0.85:
            candidate = (score, fixture)
        else:
            continue
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def _devig(values: list[float]) -> dict | None:
    try:
        inv = [1.0 / float(v) for v in values]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    total = sum(inv)
    if total <= 0:
        return None
    return {"home": inv[0] / total, "draw": inv[1] / total, "away": inv[2] / total}


def _get(base: str, path: str, params: str, timeout: int = 25) -> dict | None:
    url = f"{base}{path}?{params}"
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"Accept": "application/json"}), timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def sync_trade_date(db: Session, date: str, max_matches: int = 40) -> dict:
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置", "synced": 0}
    base = settings.sportmonks_base_url.rstrip("/")
    start, end = trade_window(date)
    matches = list(db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= start, SPMatch.kickoff <= end).limit(max_matches)).all())
    if not matches:
        return {"ok": True, "reason": "no matches", "synced": 0}

    start_day = start[:10]
    end_day = end[:10]
    fixtures: list[dict] = []
    page = 1
    while page <= 3:
        data = _get(base, f"/fixtures/between/{start_day}/{end_day}",
                    f"api_token={token}&include=participants;league&locale=zh"
                    f"&per_page=50&page={page}")
        rows = (data or {}).get("data") or []
        fixtures.extend(rows)
        if len(rows) < 50:
            break
        page += 1

    synced = 0
    unmatched: list[str] = []
    for match in matches:
        fixture = match_fixture(match, fixtures)
        if fixture is None:
            unmatched.append(match.match_no)
            continue
        fixture_id = fixture.get("id")
        probs = None
        pred = _get(base, f"/predictions/probabilities/fixtures/{fixture_id}",
                    f"api_token={token}&include=type&per_page=100")
        for row in (pred or {}).get("data") or []:
            if row.get("type_id") == 237 and row.get("predictions"):
                raw = row["predictions"]
                probs = {"home": float(raw.get("home", 0)) / 100.0,
                         "draw": float(raw.get("draw", 0)) / 100.0,
                         "away": float(raw.get("away", 0)) / 100.0}
                break
        time.sleep(0.15)

        odds = None
        bookmaker = ""
        for params in (f"api_token={token}&filters=markets:1;bookmakers:20&include=bookmaker&per_page=10",
                       f"api_token={token}&filters=markets:1&include=bookmaker&per_page=100"):
            payload = _get(base, f"/odds/pre-match/fixtures/{fixture_id}", params)
            rows = (payload or {}).get("data") or []
            grouped: dict[int, dict] = {}
            for row in rows:
                label = str(row.get("label", "")).lower()
                if label not in ("home", "draw", "away"):
                    continue
                grouped.setdefault(row.get("bookmaker_id"), {})[label] = row.get("value")
            for bid, values in grouped.items():
                if all(k in values for k in ("home", "draw", "away")):
                    de_vig = _devig([values["home"], values["draw"], values["away"]])
                    if de_vig:
                        odds = de_vig
                        bookmaker = "Pinnacle" if bid == 20 else f"书商{bid}"
                        break
            if odds:
                break
            time.sleep(0.12)

        row = db.get(SportmonksMatchData, match.match_id)
        if row is None:
            row = SportmonksMatchData(match_id=match.match_id)
            db.add(row)
        row.fixture_id = int(fixture_id)
        row.league = (fixture.get("league") or {}).get("name", "") or match.league
        row.home_name = next((p.get("name", "") for p in fixture.get("participants") or []
                              if (p.get("meta") or {}).get("location") == "home"), "")
        row.away_name = next((p.get("name", "") for p in fixture.get("participants") or []
                              if (p.get("meta") or {}).get("location") == "away"), "")
        row.kickoff_utc = fixture.get("starting_at", "")
        row.probs = probs
        row.odds = odds
        row.bookmaker = bookmaker
        row.captured_at = utcnow()
        row.data_cutoff = row.captured_at.isoformat()
        synced += 1
    db.commit()
    return {"ok": True, "reason": "done", "synced": synced,
            "unmatched": unmatched[:10], "matches": len(matches)}


def latest_for_match(db: Session, match_id: str) -> SportmonksMatchData | None:
    return db.get(SportmonksMatchData, match_id)
