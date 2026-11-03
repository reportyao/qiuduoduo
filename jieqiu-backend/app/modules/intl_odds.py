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


def sync_the_odds_api(db: Session, aligner: Aligner, now_utc: datetime,
                      api_key: str | None = None,
                      fetch_events=None) -> tuple[int, str]:
    """同步国际盘。返回 (入库条数, 说明)。key 缺失/网络失败不抛错（管线不中断）。

    fetch_events(sport_key) -> list[event]：可注入用于测试（默认调 the-odds-api）。
    """
    st = get_settings()
    key = api_key or st.odds_api_key
    if not key:
        return 0, "ODDS_API_KEY 未配置 —— 市闸将以单源 pending_data 运行"

    if fetch_events is None:
        def fetch_events(sport: str):
            url = (f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
                   f"?apiKey={urllib.parse.quote(key)}&regions=eu,uk&markets=h2h&oddsFormat=decimal")
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
    for sport in [s.strip() for s in st.odds_sports.split(",") if s.strip()]:
        try:
            events = fetch_events(sport)
        except Exception as e:
            errors.append(f"{sport}:{type(e).__name__}")
            continue
        for ev in events or []:
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
            # 选 Pinnacle（若在）否则市场共识：所有庄家去水后取均值
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
            # 按唯一键 upsert（同一场新赔率覆盖旧行 —— 市闸只看最新；SP 历史由快照表承担）
            row = db.scalar(select(IntlOdds).where(
                IntlOdds.source == source, IntlOdds.home == home,
                IntlOdds.away == away, IntlOdds.kickoff_utc == kickoff_utc))
            if row is None:
                db.add(IntlOdds(source=source, sport=sport, league=ev.get("sport_title", "") or sport,
                                home_raw=home_raw, away_raw=away_raw, home=home, away=away,
                                kickoff_utc=kickoff_utc, sp_h=sp_h, sp_d=sp_d, sp_a=sp_a,
                                retrieved_at=retrieved))
                db.flush()  # autoflush=False：立刻可见，避免同批同键再 INSERT 撞唯一
            else:
                row.sp_h, row.sp_d, row.sp_a = sp_h, sp_d, sp_a
                row.retrieved_at = retrieved
            total += 1
    db.commit()
    note = f"同步 {total} 场国际盘 @ {retrieved}"
    if errors:
        note += f"（失败 {len(errors)}：{';'.join(errors[:3])}）"
    return total, note


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
