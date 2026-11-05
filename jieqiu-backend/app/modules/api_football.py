"""API-Football（免费档优先）同步：fixtures / lineups / injuries / standings。

设计约束：
- 免费档 100 请求/日，默认只用 90；按 endpoint 持久化计数，超限即停。
- 只对已链接到竞彩场次的 fixture 拉阵容/伤停；不无限全量抓。
- 外部数据只做事实，不改判决概率；缺失就保持 missing/unknown。
- 队名自动链接依赖 team_aliases（英文别名 → 中文 canonical）；未链接由后台人工确认。
"""
from __future__ import annotations

import difflib
import re
import threading
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (ApiFootballFixture, ApiFootballUsage, MatchInjury,
                      MatchLineup, SPMatch, TeamAlias, TeamStanding)
from .align import normalize
from .timeutil import CN


class ApiFootballError(RuntimeError):
    pass


class ApiFootballNotConfigured(ApiFootballError):
    pass


class ApiFootballBudgetExceeded(ApiFootballError):
    pass


_STOP_TOKENS = {
    "fc", "cf", "sc", "afc", "club", "football", "soccer", "the",
    "足球俱乐部", "足球", "俱乐部",
}
_QUOTA_LOCK = threading.Lock()


def norm_name(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value)).lower()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    tokens = [t for t in text.split() if t and t not in _STOP_TOKENS]
    return "".join(tokens)


def _settings():
    return get_settings()


def configured() -> bool:
    return bool(_settings().api_football_key)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _to_cn(value: str | None) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CN).strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now(CN).strftime("%Y-%m-%d")


def _usage_total(db: Session, day: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(ApiFootballUsage.count), 0))
                         .where(ApiFootballUsage.day == day)) or 0)


def consume_quota(db: Session, endpoint: str) -> None:
    """调用前占一次免费额度；同进程加锁，跨进程仍由单 cron 约束。"""
    st = _settings()
    day = _today()
    with _QUOTA_LOCK:
        if _usage_total(db, day) >= st.api_football_daily_limit:
            raise ApiFootballBudgetExceeded(f"API-Football 日额度已用尽（{st.api_football_daily_limit}）")
        row = db.scalar(select(ApiFootballUsage).where(
            ApiFootballUsage.day == day, ApiFootballUsage.endpoint == endpoint))
        if row is None:
            row = ApiFootballUsage(day=day, endpoint=endpoint, count=1)
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                row = db.scalar(select(ApiFootballUsage).where(
                    ApiFootballUsage.day == day, ApiFootballUsage.endpoint == endpoint))
                if row is not None:
                    row.count += 1
                    db.commit()
        else:
            row.count += 1
            db.commit()


def _base_url_and_headers(st) -> tuple[str, dict]:
    """兼容两种来源：API-Sports 直连 key 与 RapidAPI 订阅 key。"""
    provider = (getattr(st, "api_football_provider", "apisports") or "apisports").lower()
    base = st.api_football_base_url.rstrip("/")
    if provider == "rapidapi":
        if "api-sports.io" in base:
            base = "https://api-football-v1.p.rapidapi.com/v3"
        return base, {
            "x-rapidapi-key": st.api_football_key,
            "x-rapidapi-host": getattr(st, "api_football_rapidapi_host",
                                       "api-football-v1.p.rapidapi.com"),
            "Accept": "application/json",
        }
    return base, {"x-apisports-key": st.api_football_key,
                  "Accept": "application/json"}


def _request(db: Session, endpoint: str, params: dict | None = None) -> list[dict]:
    st = _settings()
    if not st.api_football_key:
        raise ApiFootballNotConfigured("JQ_API_FOOTBALL_KEY 未配置")
    consume_quota(db, endpoint)
    base, headers = _base_url_and_headers(st)
    url = f"{base}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=st.api_football_timeout_s) as client:
            resp = client.get(url, params=params or {}, headers=headers)
            resp.raise_for_status()
            try:
                payload = resp.json()
            except ValueError as exc:
                raise ApiFootballError("API-Football 返回非 JSON") from exc
    except httpx.HTTPError as exc:
        raise ApiFootballError(f"API-Football 请求失败: {exc}") from exc
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if isinstance(errors, dict):
        errors = {k: v for k, v in errors.items() if v}
    if errors:
        raise ApiFootballError(f"API-Football 返回错误: {errors}")
    response = payload.get("response") if isinstance(payload, dict) else None
    return response if isinstance(response, list) else []


def _alias_canonical(db: Session, api_name: str) -> str | None:
    keys = {k for k in (normalize(api_name), norm_name(api_name)) if k}
    if not keys:
        return None
    row = db.scalar(select(TeamAlias).where(TeamAlias.alias.in_(keys)).limit(1))
    return row.canonical if row else None


def _name_score(candidate: str | None, api_name: str | None, db: Session) -> float:
    left_raw = candidate or ""
    right_raw = api_name or ""
    left_variants = {v for v in (norm_name(left_raw), normalize(left_raw)) if v}
    right_variants = {v for v in (norm_name(right_raw), normalize(right_raw)) if v}
    if not left_variants or not right_variants:
        return 0.0
    if left_variants & right_variants:
        return 1.0
    # 两侧都可能是别名（竞彩“莱红牛”和 API “RB Leipzig”）。
    left_canonical = _alias_canonical(db, left_raw)
    if left_canonical:
        left_variants |= {v for v in (norm_name(left_canonical),
                                      normalize(left_canonical)) if v}
    canonical = _alias_canonical(db, right_raw)
    if canonical:
        canonical_variants = {v for v in (norm_name(canonical), normalize(canonical)) if v}
        if canonical_variants & left_variants:
            return 1.0
    return max(difflib.SequenceMatcher(None, left, right).ratio()
               for left in left_variants for right in right_variants)


def _auto_link(db: Session, fixture: ApiFootballFixture) -> tuple[str | None, str, float]:
    """按开赛 ±20 分钟 + 双方队名相似度自动链接；低置信度留人工。"""
    kickoff = _to_cn(fixture.kickoff_utc)
    if not kickoff:
        return None, "none", 0.0
    k = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S")
    lo = (k - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    hi = (k + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    candidates = list(db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= lo, SPMatch.kickoff <= hi)).all())
    best_valid: tuple[SPMatch | None, float] = (None, 0.0)
    best_any = 0.0
    for match in candidates:
        hs = max(_name_score(match.home, fixture.home_name, db),
                 _name_score(match.home_raw, fixture.home_name, db))
        as_ = max(_name_score(match.away, fixture.away_name, db),
                  _name_score(match.away_raw, fixture.away_name, db))
        confidence = round((hs + as_) / 2, 3)
        best_any = max(best_any, confidence)
        within_10m = abs(
            (datetime.strptime(match.kickoff, "%Y-%m-%d %H:%M:%S") - k).total_seconds()
        ) <= 600
        if hs >= 0.92 and as_ >= 0.92 and within_10m and confidence > best_valid[1]:
            best_valid = (match, confidence)
    if best_valid[0] is not None:
        return best_valid[0].match_id, "auto", max(best_valid[1], 0.95)
    return None, "none", best_any


def _upsert_fixture(db: Session, item: dict) -> ApiFootballFixture | None:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    status = fixture.get("status") or {}
    try:
        fid = int(fixture.get("id"))
    except (TypeError, ValueError):
        return None
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    row = db.get(ApiFootballFixture, fid)
    if row is None:
        row = ApiFootballFixture(fixture_id=fid, raw=item)
        db.add(row)
    row.league_id = int(league.get("id") or 0)
    row.league_name = str(league.get("name") or "")
    row.season = int(league.get("season") or 0)
    row.home_team_id = int(home.get("id") or 0)
    row.home_name = str(home.get("name") or "")
    row.away_team_id = int(away.get("id") or 0)
    row.away_name = str(away.get("name") or "")
    row.kickoff_utc = str(fixture.get("date") or "")
    row.status_short = str(status.get("short") or "")
    row.status_long = str(status.get("long") or "")
    row.venue = str((fixture.get("venue") or {}).get("name") or "")
    row.raw = item
    row.synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if not row.match_id:
        match_id, method, confidence = _auto_link(db, row)
        row.match_id = match_id
        row.link_method = method
        row.link_confidence = confidence
    return row


def sync_fixtures(db: Session, date: str) -> dict:
    """拉取指定日期 fixtures；返回同步/链接统计。"""
    items = _request(db, "fixtures", {"date": date, "timezone": "Asia/Shanghai"})
    linked = 0
    for item in items:
        row = _upsert_fixture(db, item)
        if row is not None and row.match_id:
            linked += 1
    db.commit()
    return {"fixtures": len(items), "linked": linked}


def link_fixture(db: Session, fixture_id: int, match_id: str,
                 method: str = "manual") -> dict:
    match_id = (match_id or "").strip()
    if not match_id or len(match_id) > 32:
        raise ApiFootballError("invalid match_id")
    fixture = db.get(ApiFootballFixture, fixture_id)
    match = db.get(SPMatch, match_id)
    if fixture is None:
        raise ApiFootballError("fixture not found")
    if match is None:
        raise ApiFootballError("match not found")
    fixture.match_id = match_id
    fixture.link_method = method
    fixture.link_confidence = 1.0
    for row in db.scalars(select(MatchLineup).where(MatchLineup.fixture_id == fixture_id)):
        row.match_id = match_id
    for row in db.scalars(select(MatchInjury).where(MatchInjury.fixture_id == fixture_id)):
        row.match_id = match_id
    db.commit()
    return {"fixture_id": fixture_id, "match_id": match_id, "method": method}


def _linked_fixtures(db: Session, hours: int | None = None) -> list[ApiFootballFixture]:
    rows = list(db.scalars(select(ApiFootballFixture)
                           .where(ApiFootballFixture.match_id.isnot(None))
                           .order_by(ApiFootballFixture.kickoff_utc)).all())
    if hours is None:
        return rows
    now = datetime.now(CN)
    out = []
    for row in rows:
        kickoff = _to_cn(row.kickoff_utc)
        if not kickoff:
            continue
        dt = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
        if now - timedelta(hours=2) <= dt <= now + timedelta(hours=hours):
            out.append(row)
    return out


def sync_lineups(db: Session, hours: int | None = None,
                 max_requests: int | None = None) -> dict:
    st = _settings()
    limit = max_requests or st.api_football_max_requests_per_run
    fixtures = _linked_fixtures(db, hours or st.api_football_lineup_hours)
    done = 0
    total_rows = 0
    errors: list[str] = []
    for fixture in fixtures:
        if done >= limit:
            break
        if fixture.lineups_synced_at and (
                datetime.now(timezone.utc).replace(tzinfo=None) - fixture.lineups_synced_at
        ).total_seconds() < 20 * 60:
            continue
        try:
            items = _request(db, "fixtures/lineups", {"fixture": fixture.fixture_id})
        except ApiFootballBudgetExceeded as exc:
            errors.append(str(exc))
            break
        except ApiFootballError as exc:
            errors.append(str(exc))
            continue
        # 阵容是整场快照：成功返回后先清掉旧行，避免上一版多出的球员/边路残留。
        db.execute(delete(MatchLineup).where(
            MatchLineup.fixture_id == fixture.fixture_id))
        stored = 0
        for item in items:
            team = item.get("team") or {}
            tid = int(team.get("id") or 0)
            if not tid:
                continue
            side = "home" if tid == fixture.home_team_id else "away" if tid == fixture.away_team_id else ""
            starters = []
            for entry in item.get("startXI") or []:
                player = entry.get("player") or {}
                starters.append({
                    "id": player.get("id"), "name": player.get("name"),
                    "number": player.get("number"), "pos": player.get("pos"),
                })
            subs = []
            for entry in item.get("substitutes") or []:
                player = entry.get("player") or {}
                subs.append({"id": player.get("id"), "name": player.get("name")})
            row = db.scalar(select(MatchLineup).where(
                MatchLineup.fixture_id == fixture.fixture_id,
                MatchLineup.team_id == tid))
            if row is None:
                row = MatchLineup(fixture_id=fixture.fixture_id, team_id=tid)
                db.add(row)
            row.match_id = fixture.match_id or ""
            row.team_name = str(team.get("name") or "")
            row.side = side
            row.formation = str(item.get("formation") or "")
            row.coach = str((item.get("coach") or {}).get("name") or "")
            row.starters = starters
            row.subs = subs
            row.synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
            stored += 1
        fixture.lineups_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        # 接口在赛前可能返回空数组；不要把它算成“已同步”，否则后台计数会虚高。
        total_rows += stored
        if stored:
            done += 1
    return {"fixtures": len(fixtures), "synced": done, "rows": total_rows, "errors": errors}


def sync_injuries(db: Session, hours: int | None = None,
                  max_requests: int | None = None) -> dict:
    st = _settings()
    limit = max_requests or st.api_football_max_requests_per_run
    fixtures = _linked_fixtures(db, hours or 24)
    done = 0
    errors: list[str] = []
    for fixture in fixtures:
        if done >= limit:
            break
        if fixture.injuries_synced_at and (
                datetime.now(timezone.utc).replace(tzinfo=None) - fixture.injuries_synced_at
        ).total_seconds() < 6 * 3600:
            continue
        try:
            items = _request(db, "injuries", {"fixture": fixture.fixture_id})
        except ApiFootballBudgetExceeded as exc:
            errors.append(str(exc))
            break
        except ApiFootballError as exc:
            errors.append(str(exc))
            continue
        db.execute(delete(MatchInjury).where(MatchInjury.fixture_id == fixture.fixture_id))
        seen: set[tuple[int, str]] = set()
        for item in items:
            team = item.get("team") or {}
            player = item.get("player") or {}
            tid = int(team.get("id") or 0)
            player_id = int(player.get("id") or 0)
            if not tid or not player_id:
                continue
            # API-Football v3 把 type/reason 放在 player 内；兼容部分旧快照的顶层字段。
            injury_type = player.get("type") or item.get("type") or ""
            injury_reason = player.get("reason") or item.get("reason") or ""
            key = (player_id, str(injury_type))
            if key in seen:
                # 同一球员同类型伤停可能在接口里重复出现，唯一键只允许一条。
                continue
            seen.add(key)
            fixture_info = item.get("fixture") or {}
            db.add(MatchInjury(
                fixture_id=fixture.fixture_id, match_id=fixture.match_id or "",
                team_id=tid, team_name=str(team.get("name") or ""),
                side="home" if tid == fixture.home_team_id else "away" if tid == fixture.away_team_id else "",
                player_id=player_id,
                player_name=str(player.get("name") or ""),
                type=str(injury_type),
                reason=str(injury_reason),
                status=str(fixture_info.get("status") or ""),
            ))
        fixture.injuries_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.commit()
        except IntegrityError as exc:
            # 单场脏数据不能拖垮整批同步；回滚后保留错误，继续下一场。
            db.rollback()
            errors.append(f"fixture {fixture.fixture_id}: {type(exc).__name__}")
            continue
        done += 1
    return {"fixtures": len(fixtures), "synced": done, "errors": errors}


def sync_standings(db: Session, max_requests: int | None = None) -> dict:
    st = _settings()
    limit = max_requests or st.api_football_max_requests_per_run
    fixtures = _linked_fixtures(db)
    seen: set[tuple[int, int]] = set()
    done = 0
    errors: list[str] = []
    for fixture in fixtures:
        key = (fixture.league_id, fixture.season)
        if key in seen or not all(key):
            continue
        seen.add(key)
        if done >= limit:
            break
        try:
            items = _request(db, "standings", {"league": key[0], "season": key[1]})
        except ApiFootballBudgetExceeded as exc:
            errors.append(str(exc))
            break
        except ApiFootballError as exc:
            errors.append(str(exc))
            continue
        for group in items:
            for league in (group.get("league") or {}).get("standings") or []:
                for entry in league:
                    team = entry.get("team") or {}
                    all_stats = entry.get("all") or {}
                    goals = all_stats.get("goals") or {}
                    tid = int(team.get("id") or 0)
                    if not tid:
                        continue
                    row = db.scalar(select(TeamStanding).where(
                        TeamStanding.league_id == key[0], TeamStanding.season == key[1],
                        TeamStanding.team_id == tid))
                    if row is None:
                        row = TeamStanding(league_id=key[0], season=key[1], team_id=tid)
                        db.add(row)
                    row.team_name = str(team.get("name") or "")
                    row.rank = int(entry.get("rank") or 0)
                    row.points = int(entry.get("points") or 0)
                    row.played = int(all_stats.get("played") or 0)
                    row.wins = int(all_stats.get("win") or 0)
                    row.draws = int(all_stats.get("draw") or 0)
                    row.losses = int(all_stats.get("lose") or 0)
                    row.goals_for = int(goals.get("for") or 0)
                    row.goals_against = int(goals.get("against") or 0)
                    row.form = str(entry.get("form") or "")
                    row.synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        done += 1
    return {"leagues": len(seen), "synced": done, "errors": errors}


def sync_enrich(db: Session, lineups_max: int = 2,
                injuries_max: int = 1) -> dict:
    """只补阵容/伤停，不拉 fixtures/standings。

    免费档按日限流；这个入口给高频 cron 用，单次请求数必须很小，
    并且 sync_lineups/sync_injuries 内部已有 20min/6h 去重。
    """
    out: dict = {"lineups": {}, "injuries": {}, "errors": []}
    for key, fn, limit in (("lineups", sync_lineups, lineups_max),
                           ("injuries", sync_injuries, injuries_max)):
        try:
            out[key] = fn(db, max_requests=limit)
        except ApiFootballBudgetExceeded as exc:
            out["errors"].append(str(exc))
            out[key] = {"error": str(exc)}
            break
        except ApiFootballError as exc:
            out["errors"].append(str(exc))
            out[key] = {"error": str(exc)}
    return out


def sync_all(db: Session, date: str | None = None,
             include_next_day: bool = False) -> dict:
    d = date or _today()
    out = {"date": d, "configured": configured(), "fixtures": {}, "lineups": {},
           "injuries": {}, "standings": {}}
    try:
        fixtures = sync_fixtures(db, d)
        if include_next_day:
            nxt = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            more = sync_fixtures(db, nxt)
            fixtures = {"fixtures": fixtures.get("fixtures", 0) + more.get("fixtures", 0),
                        "linked": fixtures.get("linked", 0) + more.get("linked", 0)}
            out["next_date"] = nxt
        out["fixtures"] = fixtures
    except ApiFootballNotConfigured as exc:
        out["configured"] = False
        out["error"] = str(exc)
        return out
    except ApiFootballBudgetExceeded as exc:
        out["fixtures"] = {"error": str(exc)}
        out["error"] = str(exc)
        return out
    except ApiFootballError as exc:
        out["fixtures"] = {"error": str(exc)}
    for key, fn in (("lineups", sync_lineups), ("injuries", sync_injuries),
                    ("standings", sync_standings)):
        try:
            out[key] = fn(db)
        except ApiFootballBudgetExceeded as exc:
            out[key] = {"error": str(exc)}
            out["error"] = str(exc)
            break
        except ApiFootballError as exc:
            # 单个数据源失败不阻塞其他已链接场次的阵容/积分榜同步。
            out[key] = {"error": str(exc)}
    return out


def status(db: Session) -> dict:
    day = _today()
    st = _settings()
    total = _usage_total(db, day)
    fixtures = int(db.scalar(select(func.count()).select_from(ApiFootballFixture)) or 0)
    linked = int(db.scalar(select(func.count()).select_from(ApiFootballFixture)
                           .where(ApiFootballFixture.match_id.isnot(None))) or 0)
    lineups = int(db.scalar(select(func.count()).select_from(MatchLineup)) or 0)
    injuries = int(db.scalar(select(func.count()).select_from(MatchInjury)) or 0)
    standings = int(db.scalar(select(func.count()).select_from(TeamStanding)) or 0)
    last = db.scalar(select(func.max(ApiFootballFixture.synced_at)))
    return {
        "configured": bool(st.api_football_key),
        "base_url": _base_url_and_headers(st)[0],
        "provider": getattr(st, "api_football_provider", "apisports"),
        "daily_limit": st.api_football_daily_limit,
        "used_today": total,
        "remaining": max(0, st.api_football_daily_limit - total),
        "fixtures": fixtures,
        "linked": linked,
        "unlinked": max(0, fixtures - linked),
        "lineups": lineups,
        "injuries": injuries,
        "standings": standings,
        "last_sync": last.isoformat() if last else None,
    }
