"""Sportmonks 结构化赛前情报同步。

把 fixture 级别的阵容、阵型、伤停、积分榜、H2H、场地、天气、裁判、教练、
match-facts、预测维度和选定市场落库。只做展示/情报，不把第三方预测冒充本产品
模型；所有事实带 captured_at，前端可标注“已公布/预计”。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (SPMatch, SportmonksFixtureIntel, SportmonksMarket,
                      SportmonksPrediction, utcnow)
from .sportmonks import _get

log = logging.getLogger(__name__)
CN = timezone(timedelta(hours=8))
INTEL_TTL = timedelta(hours=6)
_POSITION = {24: "门将", 25: "后卫", 26: "中场", 27: "前锋"}
_REFEREE_ROLE = {6: "主裁", 7: "助理裁判", 8: "第四官员", 9: "VAR"}
SECTION_TTL = {
    "meta": 86400,
    "lineups": 1800,
    "standings": 21600,
    "h2h": 86400,
    "conditions": 3600,
    "predictions": 900,
    "markets": 900,
    "news": 1800,
}
_WEATHER_CN = {
    "clear sky": "晴",
    "few clouds": "少云",
    "scattered clouds": "晴间多云",
    "broken clouds": "多云",
    "overcast clouds": "阴",
    "light rain": "小雨",
    "moderate rain": "中雨",
    "heavy rain": "大雨",
    "rain": "雨",
    "thunderstorm": "雷雨",
    "mist": "薄雾",
    "fog": "雾",
    "snow": "雪",
}
_REF_CACHE: dict[int, dict] = {}
_PLAYER_CACHE: dict[int, dict] = {}
_STANDINGS_CACHE: dict[str, list[dict]] = {}


def _now() -> datetime:
    return utcnow()


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _participants(fixture: dict) -> tuple[dict[str, dict], dict[int, str]]:
    by_side: dict[str, dict] = {}
    by_team: dict[int, str] = {}
    for row in fixture.get("participants") or []:
        side = (row.get("meta") or {}).get("location") or ""
        if side not in ("home", "away"):
            continue
        by_side[side] = row
        if row.get("id"):
            by_team[int(row["id"])] = side
    return by_side, by_team


def _name(row: dict | None) -> str:
    return str((row or {}).get("name") or (row or {}).get("display_name") or "")


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value) -> float | None:
    raw = _num(value)
    return round(raw, 2) if raw is not None else None


def _referee(referee_id: int) -> dict:
    cached = _REF_CACHE.get(referee_id)
    if cached is not None:
        return cached
    from ..config import get_settings
    settings = get_settings()
    payload = _get(
        settings.sportmonks_base_url.rstrip("/"),
        "/referees/{id}".format(id=referee_id),
        "api_token={token}".format(token=settings.sportmonks_token.strip()),
    )
    data = (payload or {}).get("data") or {}
    out = {"id": referee_id, "name": _name(data) or f"裁判 {referee_id}"}
    _REF_CACHE[referee_id] = out
    return out


def _player(player_id: int) -> dict:
    cached = _PLAYER_CACHE.get(player_id)
    if cached is not None:
        return cached
    from ..config import get_settings
    settings = get_settings()
    payload = _get(
        settings.sportmonks_base_url.rstrip("/"),
        "/players/{id}".format(id=player_id),
        "api_token={token}".format(token=settings.sportmonks_token.strip()),
    )
    data = (payload or {}).get("data") or {}
    out = {"id": player_id, "name": _name(data) or f"球员 {player_id}",
           "position_id": data.get("position_id")}
    _PLAYER_CACHE[player_id] = out
    return out


def _fetch_fixture(base: str, token: str, fixture_id: int) -> dict:
    payload = _get(
        base,
        "/fixtures/{id}".format(id=fixture_id),
        "api_token={token}&include=participants;league;season;round;coaches;"
        "referees;sidelined;lineups;formations;venue;weatherReport;"
        "expectedLineups;prematchNews&locale=zh".format(token=token),
    )
    return (payload or {}).get("data") or {}


def _lineups(fixture: dict, by_side: dict[str, dict],
             by_team: dict[int, str]) -> dict:
    formations = {
        row.get("participant_id"): row.get("formation")
        for row in fixture.get("formations") or []
    }
    out = {}
    for side in ("home", "away"):
        team = by_side.get(side) or {}
        out[side] = {
            "team_id": team.get("id"),
            "team_name": _name(team),
            "formation": formations.get(team.get("id")) or "",
            "starters": [],
            "subs": [],
        }
    for row in fixture.get("lineups") or []:
        side = by_team.get(row.get("team_id") or 0)
        if side not in out:
            continue
        item = {
            "player_id": row.get("player_id"),
            "name": row.get("player_name") or "",
            "number": row.get("jersey_number"),
            "position_id": row.get("position_id"),
            "position": _POSITION.get(row.get("position_id"), ""),
            "formation_field": row.get("formation_field") or "",
            "formation_position": row.get("formation_position"),
        }
        bucket = "starters" if row.get("type_id") == 11 else "subs"
        out[side][bucket].append(item)
    for side in out.values():
        side["starters"].sort(
            key=lambda item: (item.get("formation_position") or 99, item.get("number") or 99))
        side["subs"].sort(key=lambda item: item.get("number") or 99)
    return out


def _referees(fixture: dict) -> dict:
    rows = fixture.get("referees") or []
    main_row = next((row for row in rows if row.get("type_id") == 6), rows[0] if rows else None)
    main = None
    if main_row and main_row.get("referee_id"):
        main = _referee(int(main_row["referee_id"]))
        main["role"] = _REFEREE_ROLE.get(main_row.get("type_id"), "主裁")
    return {
        "main": main,
        "crew_count": len(rows),
        "crew": [
            {"referee_id": row.get("referee_id"),
             "role": _REFEREE_ROLE.get(row.get("type_id"), "裁判")}
            for row in rows
        ],
    }


def _coaches(fixture: dict, by_side: dict[str, dict]) -> dict:
    out = {}
    for row in fixture.get("coaches") or []:
        participant_id = (row.get("meta") or {}).get("participant_id")
        side = next((key for key, team in by_side.items()
                     if team.get("id") == participant_id), None)
        if side is None:
            continue
        out[side] = {
            "name": row.get("name") or row.get("common_name") or "",
            "common_name": row.get("common_name") or "",
            "image": row.get("image_path") or "",
        }
    return out


def _sidelined(fixture: dict, by_side: dict[str, dict]) -> list[dict]:
    team_side = {team.get("id"): side for side, team in by_side.items()}
    out = []
    for row in fixture.get("sidelined") or []:
        player_id = row.get("player_id")
        if not player_id:
            continue
        player = _player(int(player_id))
        team_id = row.get("participant_id")
        type_id = int(row.get("type_id") or 0)
        out.append({
            "player_id": player_id,
            "player_name": player.get("name") or "",
            "side": team_side.get(team_id, ""),
            "team_id": team_id,
            "type_id": type_id,
            "type_label": "伤停" if type_id == 551 else "缺阵",
        })
    return out


def _standings(round_id, season_id, home_id, away_id, token: str, base: str) -> dict:
    if not (round_id or season_id):
        return {"round_id": round_id, "season_id": season_id, "home": None, "away": None}
    key = f"round:{round_id}" if round_id else f"season:{season_id}"
    rows = _STANDINGS_CACHE.get(key)
    if rows is None:
        params = "api_token={token}&include=participant;form;details&per_page=50&locale=zh".format(
            token=token)
        path = f"/standings/rounds/{round_id}" if round_id else f"/standings/seasons/{season_id}"
        payload = _get(base, path, params)
        rows = (payload or {}).get("data") or []
        _STANDINGS_CACHE[key] = rows
    by_id = {}
    for row in rows:
        details = {str(item.get("type_id")): item.get("value")
                   for item in row.get("details") or []}
        form = [
            item.get("form") for item in sorted(
                row.get("form") or [], key=lambda item: item.get("sort_order") or 0,
                reverse=True)
        ]
        by_id[row.get("participant_id")] = {
            "position": row.get("position"),
            "points": row.get("points"),
            "played": details.get("129"),
            "won": details.get("130"),
            "drawn": details.get("131"),
            "lost": details.get("132"),
            "goals_for": details.get("133"),
            "goals_against": details.get("134"),
            "goal_diff": details.get("179"),
            "form": [value for value in form if value],
        }
    return {
        "round_id": round_id,
        "season_id": season_id,
        "home": by_id.get(home_id),
        "away": by_id.get(away_id),
    }


def _scores(row: dict) -> dict[int, int]:
    current: dict[int, int] = {}
    halves: dict[int, int] = {}
    for item in row.get("scores") or []:
        score = item.get("score") or {}
        goals = score.get("goals")
        if goals is None:
            continue
        participant_id = item.get("participant_id")
        if participant_id is None:
            continue
        if item.get("type_id") == 1525:
            current[participant_id] = int(goals)
        elif item.get("type_id") in (1, 2):
            halves[participant_id] = halves.get(participant_id, 0) + int(goals)
    return current or halves


def _fixture_result(row: dict) -> dict | None:
    parts, _ = _participants(row)
    home = parts.get("home") or {}
    away = parts.get("away") or {}
    score = _scores(row)
    home_id, away_id = home.get("id"), away.get("id")
    if not home_id or not away_id or home_id not in score or away_id not in score:
        return None
    return {
        "id": row.get("id"),
        "date": (row.get("starting_at") or "")[:10],
        "home": _name(home),
        "away": _name(away),
        "score_home": score[home_id],
        "score_away": score[away_id],
        "result": row.get("result_info") or "",
        "league": (row.get("league") or {}).get("name") or "",
    }


def _h2h(home_id, away_id, base: str, token: str) -> list[dict]:
    payload = _get(
        base,
        f"/fixtures/head-to-head/{home_id}/{away_id}",
        "api_token={token}&include=participants;league;scores&per_page=10&locale=zh".format(
            token=token),
    )
    out = []
    for row in (payload or {}).get("data") or []:
        item = _fixture_result(row)
        if item:
            out.append(item)
    return out[:6]


def _facts(fixture_id: int, base: str, token: str) -> list[dict]:
    payload = _get(
        base,
        f"/match-facts/{fixture_id}",
        "api_token={token}&include=type&per_page=100&locale=zh".format(token=token),
    )
    out = []
    for row in (payload or {}).get("data") or []:
        text = row.get("natural_language")
        if not text:
            continue
        type_info = row.get("type") or {}
        out.append({
            "type_id": row.get("type_id"),
            "type_code": type_info.get("code") or "",
            "type_name": type_info.get("name") or "",
            "category": row.get("category") or "",
            "scope": row.get("scope") or "",
            "basis": row.get("basis") or "",
            "text": str(text)[:240],
        })
    return out


def _predictions(fixture_id: int, base: str, token: str) -> tuple[list[dict], dict]:
    payload = _get(
        base,
        f"/predictions/probabilities/fixtures/{fixture_id}",
        "api_token={token}&include=type&per_page=100&locale=zh".format(token=token),
    )
    rows = (payload or {}).get("data") or []
    items = []
    by_code: dict[str, dict] = {}
    for row in rows:
        type_info = row.get("type") or {}
        code = (type_info.get("developer_name") or type_info.get("code")
                or f"TYPE_{row.get('type_id')}")
        item = {
            "type_id": row.get("type_id"),
            "type_code": code,
            "type_name": type_info.get("name") or code,
            "probabilities": row.get("predictions") or {},
        }
        items.append(item)
        by_code[code] = item
    highlights = []
    for code, label in (
        ("BTTS_PROBABILITY", "双方进球"),
        ("OVER_UNDER_2_5_PROBABILITY", "大小球 2.5"),
        ("DOUBLE_CHANCE_PROBABILITY", "双重机会"),
        ("FIRST_HALF_WINNER_PROBABILITY", "半场胜平负"),
        ("TEAM_TO_SCORE_FIRST_PROBABILITY", "先得分球队"),
    ):
        item = by_code.get(code)
        if item:
            highlights.append({"key": code, "label": label,
                               "values": item["probabilities"]})
    score_item = by_code.get("CORRECT_SCORE_PROBABILITY")
    scores = (score_item or {}).get("probabilities", {}).get("scores") or {}
    if scores:
        top = sorted(
            ((key, _num(value)) for key, value in scores.items()
             if _num(value) is not None and not str(key).startswith("Other")),
            key=lambda pair: pair[1] or 0, reverse=True,
        )[:3]
        highlights.append({
            "key": "CORRECT_SCORE_PROBABILITY",
            "label": "正确比分",
            "scores": [{"score": key, "probability": value} for key, value in top],
        })
    return items, {"items": highlights}


def _market_board(fixture_id: int, base: str, token: str) -> list[dict]:
    payload = _get(
        base,
        f"/odds/pre-match/fixtures/{fixture_id}",
        "api_token={token}&filters=bookmakers:20&per_page=1000&locale=zh".format(token=token),
    )
    rows = (payload or {}).get("data") or []
    board: list[dict] = []
    label_cn = {"home": "主胜", "draw": "平局", "away": "客胜",
                "over": "大", "under": "小"}
    for market_id, key, name in (
        (1, "1x2", "胜平负"),
        (6, "ah", "亚洲让球"),
        (80, "ou", "大小球"),
    ):
        subset = [row for row in rows if row.get("market_id") == market_id]
        if not subset:
            continue
        line = ""
        if market_id == 6:
            lines = [str(row.get("handicap")) for row in subset if row.get("handicap") is not None]
            line = min(lines, key=lambda value: abs(_num(value) or 99)) if lines else ""
            subset = [row for row in subset if str(row.get("handicap")) == line]
        elif market_id == 80:
            line = "2.5"
            subset = [row for row in subset if str(row.get("total")) == line]
        selections = []
        for row in subset:
            label = str(row.get("label") or "").lower()
            if label not in label_cn:
                continue
            selections.append({
                "label": label_cn[label],
                "price": _num(row.get("value")),
                "probability": _pct(str(row.get("probability") or "").replace("%", "")),
            })
        if selections:
            board.append({
                "key": key,
                "name": name,
                "bookmaker": "Pinnacle",
                "line": line,
                "selections": selections,
            })
    return board


def _weather(fixture: dict) -> dict | None:
    raw = fixture.get("weatherreport")
    if not isinstance(raw, dict) or not raw:
        return None
    description = str(raw.get("description") or "")
    return {
        "description": _WEATHER_CN.get(description.lower(), description),
        "temperature": raw.get("temperature") or {},
        "feels_like": raw.get("feels_like") or {},
        "wind": raw.get("wind") or {},
        "humidity": raw.get("humidity"),
        "clouds": raw.get("clouds"),
        "pressure": raw.get("pressure"),
    }


def _venue(fixture: dict) -> dict | None:
    raw = fixture.get("venue")
    if not isinstance(raw, dict) or not raw:
        return None
    name = str(raw.get("name") or "")
    if " --> " in name:
        name = name.split(" --> ", 1)[1].strip()
    return {
        "name": name,
        "city": raw.get("city_name") or "",
        "capacity": raw.get("capacity"),
        "surface": raw.get("surface") or "",
        "image": raw.get("image_path") or "",
    }


def _news(fixture: dict, key: str) -> list[dict]:
    raw = fixture.get(key) or []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:5]:
        if isinstance(item, dict):
            out.append({
                "title": item.get("title") or item.get("name") or "",
                "text": item.get("text") or item.get("content") or "",
            })
    return out


def _upsert_predictions(db: Session, match_id: str, items: list[dict],
                        captured: datetime) -> None:
    db.execute(delete(SportmonksPrediction).where(
        SportmonksPrediction.match_id == match_id))
    for item in items:
        db.add(SportmonksPrediction(
            match_id=match_id,
            type_id=int(item.get("type_id") or 0),
            type_code=str(item.get("type_code") or "")[:64],
            type_name=str(item.get("type_name") or "")[:128],
            probabilities=item.get("probabilities") or {},
            captured_at=captured,
        ))


def _upsert_markets(db: Session, match_id: str, items: list[dict],
                    captured: datetime) -> None:
    db.execute(delete(SportmonksMarket).where(SportmonksMarket.match_id == match_id))
    for item in items:
        db.add(SportmonksMarket(
            match_id=match_id,
            market_key=str(item.get("key") or "")[:32],
            market_name=str(item.get("name") or "")[:64],
            bookmaker=str(item.get("bookmaker") or "")[:32],
            line=str(item.get("line") or "")[:16],
            selections=item.get("selections") or [],
            captured_at=captured,
        ))


def sync_fixture_intel(db: Session, base: str, token: str,
                       match: SPMatch, fixture: dict) -> dict:
    """同步一场的 P0/P1 情报；失败只记录，不拖垮 SP/市场主链。"""
    fixture_id = int(fixture.get("id") or 0)
    if not fixture_id:
        return {"ok": False, "reason": "missing_fixture_id"}
    detailed = _fetch_fixture(base, token, fixture_id)
    if not detailed:
        return {"ok": False, "reason": "fixture_not_visible"}
    now = _now()
    by_side, by_team = _participants(detailed)
    home = by_side.get("home") or {}
    away = by_side.get("away") or {}
    home_id, away_id = home.get("id"), away.get("id")
    lineups = _lineups(detailed, by_side, by_team)
    standings = _standings(
        detailed.get("round_id"), detailed.get("season_id"),
        home_id, away_id, token, base,
    ) if home_id and away_id else {}
    h2h = _h2h(home_id, away_id, base, token) if home_id and away_id else []
    predictions, highlights = _predictions(fixture_id, base, token)
    markets = _market_board(fixture_id, base, token)
    facts = _facts(fixture_id, base, token)
    payload = {
        "schema": "sportmonks-intel-v1",
        "fixture_id": fixture_id,
        "league": (detailed.get("league") or {}).get("name") or match.league,
        "season": {
            "id": detailed.get("season_id"),
            "name": (detailed.get("season") or {}).get("name") or "",
        },
        "round": {
            "id": detailed.get("round_id"),
            "name": (detailed.get("round") or {}).get("name") or "",
        },
        "venue": _venue(detailed),
        "weather": _weather(detailed),
        "coaches": _coaches(detailed, by_side),
        "referees": _referees(detailed),
        "formations": {
            "home": (lineups.get("home") or {}).get("formation") or "",
            "away": (lineups.get("away") or {}).get("formation") or "",
        },
        "lineups": lineups,
        "sidelined": _sidelined(detailed, by_side),
        "standings": standings,
        "h2h": h2h,
        "recent": {
            "home": (standings.get("home") or {}).get("form") or [],
            "away": (standings.get("away") or {}).get("form") or [],
        },
        "match_facts": facts,
        "prediction_highlights": highlights,
        "market_board": markets,
        "expected_lineups": len(detailed.get("expectedlineups") or []),
        "prematch_news": _news(detailed, "prematchnews"),
        "section_meta": {
            key: {"captured_at": _iso(now), "ttl_seconds": ttl}
            for key, ttl in SECTION_TTL.items()
        },
        "data_cutoff": _iso(now),
    }
    row = db.get(SportmonksFixtureIntel, match.match_id)
    if row is None:
        row = SportmonksFixtureIntel(match_id=match.match_id)
        db.add(row)
    row.fixture_id = fixture_id
    row.league = payload["league"][:128]
    row.home_name = _name(home)[:128]
    row.away_name = _name(away)[:128]
    row.kickoff_utc = detailed.get("starting_at") or ""
    row.payload = payload
    row.captured_at = now
    row.expires_at = now + INTEL_TTL
    row.data_cutoff = payload["data_cutoff"]
    # API 偶发空响应时保留上一次有效数据，不把已有多维预测/市场清空。
    if predictions:
        _upsert_predictions(db, match.match_id, predictions, now)
    if markets:
        _upsert_markets(db, match.match_id, markets, now)
    return {
        "ok": True,
        "fixture_id": fixture_id,
        "lineups": sum(len((lineups.get(side) or {}).get("starters") or [])
                       for side in ("home", "away")),
        "facts": len(facts),
        "predictions": len(predictions),
        "markets": len(markets),
        "h2h": len(h2h),
        "standings": bool(standings.get("home") and standings.get("away")),
    }


def sync_postmatch_intel(db: Session, base: str, token: str,
                         match: SPMatch, fixture_id: int) -> bool:
    """赛后补 xG/进球时间线到已有 intel payload；不覆盖赛前阵容/积分榜。"""
    payload = _get(
        base,
        f"/fixtures/{fixture_id}",
        "api_token={token}&include=participants;league;scores;events;"
        "xGFixture;state&locale=zh".format(token=token),
    )
    data = (payload or {}).get("data") or {}
    state = str((data.get("state") or {}).get("short_name") or "").upper()
    if state not in {"FT", "AET", "PEN", "FINISHED"}:
        return False
    result = _fixture_result(data)
    row = db.get(SportmonksFixtureIntel, match.match_id)
    if result is None or row is None:
        return False
    xg: dict[str, float] = {}
    for item in data.get("xgfixture") or []:
        if int(item.get("type_id") or 0) != 5304:
            continue
        side = str(item.get("location") or "")
        value = _num((item.get("data") or {}).get("value"))
        if side in ("home", "away") and value is not None:
            xg[side] = round(value, 2)
    goals = []
    sides, _ = _participants(data)
    for event in data.get("events") or []:
        if int(event.get("type_id") or 0) != 14:
            continue
        side = next((key for key, team in sides.items()
                     if team.get("id") == event.get("participant_id")), "")
        goals.append({
            "minute": event.get("minute"),
            "player": event.get("player_name") or "",
            "side": side,
            "result": event.get("result") or "",
        })
    existing = dict(row.payload or {})
    existing["postmatch"] = {
        "score_home": result["score_home"],
        "score_away": result["score_away"],
        "xg_home": xg.get("home"),
        "xg_away": xg.get("away"),
        "goals": goals[:20],
        "captured_at": _iso(),
    }
    row.payload = existing
    return True


def latest_intel(db: Session, match_id: str) -> SportmonksFixtureIntel | None:
    return db.get(SportmonksFixtureIntel, match_id)


def latest_markets(db: Session, match_id: str) -> list[SportmonksMarket]:
    return list(db.scalars(select(SportmonksMarket).where(
        SportmonksMarket.match_id == match_id).order_by(SportmonksMarket.id)).all())


def latest_predictions(db: Session, match_id: str) -> list[SportmonksPrediction]:
    return list(db.scalars(select(SportmonksPrediction).where(
        SportmonksPrediction.match_id == match_id).order_by(SportmonksPrediction.type_id)).all())
