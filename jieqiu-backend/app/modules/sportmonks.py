"""Sportmonks 同步：按竞彩销售日拉 1X2 预测与市场 1X2，挂到 match_id。

设计约束：
- 只做增强，不创建竞彩场次；映射不上就跳过，绝不猜。
- 预测/赔率任一缺失也可以落库（另一项照常展示）。
- 所有请求带 locale=zh；中文名仅用于展示，映射仍按开球时间 + 名称相似度。
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AIResearch, SPMatch, SportmonksMatchData, utcnow
from .timeutil import trade_window

CN_TZ = timezone(timedelta(hours=8))
log = logging.getLogger(__name__)


def _norm(name: str) -> str:
    value = (name or "").lower()
    value = re.sub(r"[\s\-_.·,，。()（）]", "", value)
    value = value.replace("星期", "周")
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


def _char_overlap(a: str, b: str) -> float:
    """中文缩写覆盖：竞彩“谢周三” vs SM“谢菲尔德星期三”字符全覆盖。"""
    left, right = set(_norm(a)), set(_norm(b))
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


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
            # 中文缩写补充：开球 45 分钟内，一队几乎完全命中、另一队字符覆盖 ≥70%。
            minutes = abs((fk - kickoff).total_seconds()) / 60
            if minutes <= 45:
                hc = max(hs, _char_overlap(match.home, parts.get("home", "")))
                ac = max(as_, _char_overlap(match.away, parts.get("away", "")))
                if min(hc, ac) >= 0.7 and max(hc, ac) >= 0.95:
                    candidate = (hc + ac, fixture)
                else:
                    continue
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


def _fetch_fixtures(base: str, token: str, start_day: str, end_day: str) -> list[dict]:
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
    return fixtures


def _fetch_predictions(base: str, token: str, fixture_id: int) -> dict | None:
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
    return probs


def _fetch_odds(base: str, token: str, fixture_id: int) -> tuple[dict | None, str]:
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
                    return de_vig, "Pinnacle" if bid == 20 else f"书商{bid}"
        time.sleep(0.12)
    return None, ""


def _snapshot(db: Session, match: SPMatch, fixture: dict, probs: dict | None,
              odds: dict | None, bookmaker: str, source: str) -> SportmonksMatchData:
    row = db.get(SportmonksMatchData, match.match_id)
    if row is None:
        row = SportmonksMatchData(match_id=match.match_id)
        db.add(row)
    row.fixture_id = int(fixture.get("id") or 0)
    row.league = (fixture.get("league") or {}).get("name", "") or match.league
    row.home_name = next((p.get("name", "") for p in fixture.get("participants") or []
                          if (p.get("meta") or {}).get("location") == "home"), "")
    row.away_name = next((p.get("name", "") for p in fixture.get("participants") or []
                          if (p.get("meta") or {}).get("location") == "away"), "")
    row.kickoff_utc = fixture.get("starting_at", "")
    row.probs = probs
    row.odds = odds
    row.bookmaker = bookmaker
    row.source = source
    row.captured_at = utcnow()
    row.data_cutoff = row.captured_at.isoformat()
    return row


def _sync_match(db: Session, base: str, token: str, match: SPMatch,
                fixture: dict, source: str = "sportmonks") -> SportmonksMatchData:
    fixture_id = int(fixture.get("id") or 0)
    probs = _fetch_predictions(base, token, fixture_id)
    odds, bookmaker = _fetch_odds(base, token, fixture_id)
    return _snapshot(db, match, fixture, probs, odds, bookmaker, source)


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

    fixtures = _fetch_fixtures(base, token, start[:10], end[:10])
    synced = 0
    unmatched: list[str] = []
    for match in matches:
        fixture = match_fixture(match, fixtures)
        if fixture is None:
            unmatched.append(match.match_no)
            continue
        _sync_match(db, base, token, match, fixture)
        synced += 1
    db.commit()
    return {"ok": True, "reason": "done", "synced": synced,
            "unmatched": unmatched[:10], "matches": len(matches)}


def map_match(db: Session, match_id: str, fixture_id: int,
              source: str = "manual") -> dict:
    """人工把一场竞彩绑定到指定 Sportmonks fixture，并立即拉预测/赔率/情报。"""
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置"}
    match = db.get(SPMatch, match_id)
    if match is None:
        return {"ok": False, "reason": "竞彩场次不存在"}
    other = db.scalar(select(SportmonksMatchData).where(
        SportmonksMatchData.fixture_id == fixture_id,
        SportmonksMatchData.match_id != match_id))
    if other is not None:
        return {"ok": False, "reason": f"该 fixture 已映射到 {other.match_id}"}
    base = settings.sportmonks_base_url.rstrip("/")
    payload = _get(base, f"/fixtures/{fixture_id}",
                   f"api_token={token}&include=participants;league&locale=zh")
    fixture = (payload or {}).get("data")
    if not fixture:
        return {"ok": False, "reason": "Sportmonks fixture 不存在或不可见"}
    row = _sync_match(db, base, token, match, fixture, source=source)
    db.commit()
    intel_ok = False
    try:
        from .intel_research import sync_match as sync_intel
        intel_ok = bool(sync_intel(db, match_id))
    except Exception:  # noqa: BLE001 - 人工映射成功不应被情报失败回滚
        log.exception("intel refresh after manual mapping failed")
    return {"ok": True, "match_id": match_id, "fixture_id": row.fixture_id,
            "home": row.home_name, "away": row.away_name,
            "probs": bool(row.probs), "odds": bool(row.odds),
            "intel": intel_ok}


def unmap_match(db: Session, match_id: str) -> dict:
    row = db.get(SportmonksMatchData, match_id)
    if row is None:
        return {"ok": False, "reason": "该场次尚未映射"}
    db.delete(row)
    intel = db.get(AIResearch, match_id)
    if intel is not None:
        db.delete(intel)
    db.commit()
    return {"ok": True, "match_id": match_id}


def candidate_fixtures(db: Session, match_id: str) -> dict:
    """列出开球前后 6 小时内可人工绑定的 Sportmonks fixture。"""
    settings = get_settings()
    token = settings.sportmonks_token.strip()
    if not token:
        return {"ok": False, "reason": "JQ_SPORTMONKS_TOKEN 未配置", "candidates": []}
    match = db.get(SPMatch, match_id)
    if match is None:
        return {"ok": False, "reason": "竞彩场次不存在", "candidates": []}
    kickoff = _kickoff_utc(match)
    if kickoff is None:
        return {"ok": False, "reason": "开球时间格式异常", "candidates": []}
    base = settings.sportmonks_base_url.rstrip("/")
    day = match.kickoff[:10]
    prev = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    nxt = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    fixtures = _fetch_fixtures(base, token, prev, nxt)
    mapped = {r.fixture_id: r.match_id for r in db.scalars(
        select(SportmonksMatchData).where(
            SportmonksMatchData.fixture_id.in_([f.get("id") for f in fixtures]))).all()}
    candidates = []
    for fixture in fixtures:
        fk = _fixture_kickoff(fixture)
        if fk is None:
            continue
        delta_min = int((fk - kickoff).total_seconds() / 60)
        if abs(delta_min) > 360:
            continue
        parts = {p.get("meta", {}).get("location"): p.get("name", "")
                 for p in fixture.get("participants") or []}
        candidates.append({
            "fixture_id": fixture.get("id"),
            "league": (fixture.get("league") or {}).get("name", ""),
            "home": parts.get("home", ""),
            "away": parts.get("away", ""),
            "kickoff_utc": fixture.get("starting_at", ""),
            "delta_min": delta_min,
            "home_sim": round(_similar(match.home, parts.get("home", "")), 3),
            "away_sim": round(_similar(match.away, parts.get("away", "")), 3),
            "suggested": match_fixture(match, [fixture]) is not None,
            "mapped_to": mapped.get(fixture.get("id")),
        })
    candidates.sort(key=lambda c: (not c["suggested"], abs(c["delta_min"])))
    return {"ok": True, "match": {
        "match_id": match.match_id, "match_no": match.match_no,
        "home": match.home, "away": match.away, "kickoff": match.kickoff,
    }, "candidates": candidates[:20]}


def latest_for_match(db: Session, match_id: str) -> SportmonksMatchData | None:
    return db.get(SportmonksMatchData, match_id)
