"""国际盘源：the-odds-api（可插拔）。

- 免费 500 次/月；每次 seed 按 6h 节流同步
- 返回队名为英文 → aligner 对齐到规范中文后入库
- 未配置 key：返回 (0, reason)，市闸诚实 pending_data —— 不造假数据
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import IntlOdds
from .align import Aligner

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


# 竞彩中文联赛名 → The Odds API sport key。按当日场次动态选择，避免为无关联赛烧配额。
LEAGUE_SPORT_KEYS: dict[str, str] = {
    "英超": "soccer_epl",
    "英冠": "soccer_efl_champ",
    "西甲": "soccer_spain_la_liga",
    "西乙": "soccer_spain_segunda_division",
    "德甲": "soccer_germany_bundesliga",
    "德乙": "soccer_germany_bundesliga2",
    "意甲": "soccer_italy_serie_a",
    "法甲": "soccer_france_ligue_one",
    "欧冠": "soccer_uefa_champs_league",
    "欧联": "soccer_uefa_europa_league",
    "欧罗巴": "soccer_uefa_europa_league",
    "欧协联": "soccer_uefa_europa_conference_league",
    "欧会杯": "soccer_uefa_europa_conference_league",
    "苏超": "soccer_spl",
    "奥甲": "soccer_austria_bundesliga",
    "俄超": "soccer_russia_premier_league",
}


def sports_for_trade_date(db: Session, date: str | None = None) -> list[str]:
    """按当日竞彩场次的联赛名，返回需要同步的 Odds API sport key（去重、保序）。"""
    from ..models import SPMatch
    from .timeutil import trade_date_now, trade_window

    date = date or trade_date_now()
    start, end = trade_window(date)
    leagues = list(db.scalars(
        select(SPMatch.league).where(SPMatch.kickoff >= start,
                                     SPMatch.kickoff <= end)).all())
    keys: list[str] = []
    for league in leagues:
        text = (league or "").strip()
        for cn, key in LEAGUE_SPORT_KEYS.items():
            if cn in text and key not in keys:
                keys.append(key)
    return keys


def _target_matches(db: Session, date: str) -> list[dict]:
    """当天竞彩在售/在赛场次；国际盘只允许匹配这些目标。"""
    from ..models import SPMatch
    from .timeutil import trade_window

    start, end = trade_window(date)
    rows = list(db.scalars(select(SPMatch).where(
        SPMatch.kickoff >= start, SPMatch.kickoff <= end)).all())
    return [{"match_id": m.match_id, "home": m.home, "away": m.away,
             "kickoff": m.kickoff} for m in rows if m.home and m.away]


def _event_matches(ev: dict, targets: list[dict], aligner: Aligner) -> bool:
    home = aligner.resolve(ev.get("home_team", "") or "")
    away = aligner.resolve(ev.get("away_team", "") or "")
    if not home or not away:
        return False
    raw = (ev.get("commence_time") or "").replace("Z", "+00:00")
    try:
        kick = datetime.fromisoformat(raw).astimezone(CN)
    except (TypeError, ValueError):
        return False
    for target in targets:
        if home != target["home"] or away != target["away"]:
            continue
        try:
            target_kick = datetime.strptime(
                target["kickoff"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
        except ValueError:
            continue
        if abs((kick - target_kick).total_seconds()) <= 4 * 3600:
            return True
    return False


def sync_the_odds_api(db: Session, aligner: Aligner, now_utc: datetime,
                      api_key: str | None = None,
                      fetch_events=None,
                      fetch_event_list=None,
                      sports: list[str] | None = None,
                      trade_date: str | None = None) -> tuple[int, str]:
    """同步国际盘。返回 (入库条数, 说明)。key 缺失/网络失败不抛错（管线不中断）。

    生产路径先调免费的 /events 列出赛事，只对竞彩采集到的比赛请求 /odds
    （eventIds 过滤）；没有对应赛事就不花 credit。
    fetch_events/fetch_event_list 可注入用于测试；只注入 fetch_events 时保留旧行为。
    """
    st = get_settings()
    key = api_key or st.odds_api_key
    if not key:
        return 0, "ODDS_API_KEY 未配置 —— 市闸将以单源 pending_data 运行"

    legacy_fetch = fetch_events is not None and fetch_event_list is None
    if fetch_events is None:
        def fetch_events(sport: str, event_ids: list[str]):
            params = urllib.parse.urlencode({
                "apiKey": key,
                "regions": st.odds_api_regions,
                "markets": "h2h",
                "oddsFormat": "decimal",
                "eventIds": ",".join(event_ids),
            })
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?{params}"
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read().decode())

    if fetch_event_list is None:
        def fetch_event_list(sport: str):
            params = urllib.parse.urlencode({"apiKey": key})
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/?{params}"
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read().decode())

    # 6h 节流：最近一次拉取太新则跳过（省配额）
    last = db.scalar(select(IntlOdds.retrieved_at).order_by(IntlOdds.retrieved_at.desc()).limit(1))
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if (now_utc - last_dt).total_seconds() < st.odds_sync_min_interval_hours * 3600:
                return 0, f"节流：上次同步 {last_dt.isoformat()}，跳过"
        except ValueError:
            pass

    retrieved = now_utc.isoformat(timespec="seconds")
    total = 0
    errors = []
    sport_list = sports if sports is not None else [
        s.strip() for s in st.odds_sports.split(",") if s.strip()]
    if not sport_list:
        return 0, "当日联赛没有对应的 Odds API sport key —— 不请求任何比赛"
    targets = _target_matches(db, trade_date or _trade_date_cn(now_utc))
    if not targets and not legacy_fetch:
        return 0, "当日没有竞彩目标场次 —— 不请求国际盘"

    for sport in sport_list:
        try:
            if legacy_fetch:
                events = fetch_events(sport)
            else:
                listed = fetch_event_list(sport) or []
                ids = [str(ev.get("id")) for ev in listed
                       if ev.get("id") and _event_matches(ev, targets, aligner)]
                if not ids:
                    continue
                events = fetch_events(sport, ids)
        except Exception as e:
            errors.append(f"{sport}:{type(e).__name__}")
            continue
        for ev in events or []:
            if not legacy_fetch and not _event_matches(ev, targets, aligner):
                continue
            bk = {}
            for bm in ev.get("bookmakers", []):
                for mk in bm.get("markets", []):
                    if mk.get("key") != "h2h":
                        continue
                    odds = {o["name"]: float(o["price"]) for o in mk.get("outcomes", [])}
                    h = odds.get(ev.get("home_team"))
                    a = odds.get(ev.get("away_team"))
                    d = odds.get("Draw")
                    if h and a and d:
                        bk[bm["key"]] = (h, d, a)
            if not bk:
                continue
            if "pinnacle" in bk:
                sp_h, sp_d, sp_a = bk["pinnacle"]
                source = "pinnacle"
            else:
                probs = [_devig(v) for v in bk.values()]
                ph = sum(p[0] for p in probs) / len(probs)
                pd_ = sum(p[1] for p in probs) / len(probs)
                pa = sum(p[2] for p in probs) / len(probs)
                s = ph + pd_ + pa
                sp_h, sp_d, sp_a = (1 / (ph / s)), (1 / (pd_ / s)), (1 / (pa / s))
                source = "consensus"
            home_raw = ev.get("home_team", "")
            away_raw = ev.get("away_team", "")
            home = aligner.resolve(home_raw)
            away = aligner.resolve(away_raw)
            kickoff_utc = (ev.get("commence_time") or "").replace("Z", "+00:00")
            if not kickoff_utc:
                continue
            row = db.scalar(select(IntlOdds).where(
                IntlOdds.source == source, IntlOdds.home == home,
                IntlOdds.away == away, IntlOdds.kickoff_utc == kickoff_utc))
            if row is None:
                db.add(IntlOdds(source=source, sport=sport, league=ev.get("sport_title", "") or sport,
                                home_raw=home_raw, away_raw=away_raw, home=home, away=away,
                                kickoff_utc=kickoff_utc, sp_h=sp_h, sp_d=sp_d, sp_a=sp_a,
                                retrieved_at=retrieved))
                db.flush()
            else:
                row.sp_h, row.sp_d, row.sp_a = sp_h, sp_d, sp_a
                row.retrieved_at = retrieved
            total += 1
    db.commit()
    note = f"同步 {total} 场国际盘 @ {retrieved}"
    if errors:
        note += f"（失败 {len(errors)}：{';'.join(errors[:3])}）"
    return total, note


def _trade_date_cn(now_utc: datetime) -> str:
    from .timeutil import trade_date_now
    return trade_date_now(now_utc.astimezone(CN))

def _devig(sp: tuple[float, float, float]) -> tuple[float, float, float]:
    imp = [1.0 / x for x in sp]
    s = sum(imp)
    return imp[0] / s, imp[1] / s, imp[2] / s


def sources_for_match(db: Session, match) -> list[IntlOdds]:
    """该场的国际盘行（已对齐、kickoff ±4h 窗口内），供市闸与证据链使用。"""
    kickoff_cn = datetime.strptime(match.kickoff, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN)
    lo = (kickoff_cn - timedelta(hours=4)).astimezone(timezone.utc).isoformat()
    hi = (kickoff_cn + timedelta(hours=4)).astimezone(timezone.utc).isoformat()
    rows = db.scalars(
        select(IntlOdds).where(
            IntlOdds.home == match.home, IntlOdds.away == match.away,
            IntlOdds.kickoff_utc >= lo, IntlOdds.kickoff_utc <= hi,
        ).order_by(IntlOdds.retrieved_at.desc())
    ).all()
    return list(rows)
