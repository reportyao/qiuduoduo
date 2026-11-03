"""赛果同步 + 判决结算（W4）。

- 赛果源：football-data.co.uk 当季 CSV（免费、含完赛场次 FTHG/FTAG），队名经 aligner 对齐
- 结算：有 pick 的判决，按其口径（had=1x2；hhad=让球线调整）判定 win/lose，记比分
- 诚实规则：无赛果源的场次保持未结算（null），绝不推算
"""
from __future__ import annotations

import csv
import io
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import MatchResult, Verdict, utcnow
from .align import Aligner

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))

# football-data 联赛代码（当季目录 2627）
FD_LEAGUES = {
    "E0": "英超", "D1": "德甲", "SP1": "西甲", "I1": "意甲", "F1": "法甲",
}


def _seasons() -> list[str]:
    """当季 + 上季（跨年结算覆盖）。"""
    now = datetime.now(CN)
    y = now.year
    seasons = []
    for start in (y - 1, y):
        s = f"{start}{str(start + 1)[2:]}"  # e.g. 2026 → "202627"
        seasons.append(s)
    return seasons


def sync_results_football_data(db: Session, aligner: Aligner,
                               fetch=None) -> tuple[int, str]:
    """拉取当季/上季完赛场次入库。返回 (新增条数, 说明)。失败不抛错。"""
    seasons = _seasons()
    total = 0
    errors = []
    for code, cn_name in FD_LEAGUES.items():
        for season in seasons:
            url = f"https://www.football-data.co.uk/mmz4281/{season[2:]}/{code}.csv"
            try:
                if fetch is None:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    raw = urllib.request.urlopen(req, timeout=20).read()
                    text = raw.decode("windows-1252", "replace")
                else:
                    text = fetch(code, season)
            except Exception as e:
                errors.append(f"{code}/{season}:{type(e).__name__}")
                continue
            rows = list(csv.DictReader(io.StringIO(text)))
            for r in rows:
                if not r.get("FTHG") or not r.get("FTAG") or not r.get("Date"):
                    continue
                try:
                    gh, ga = int(r["FTHG"]), int(r["FTAG"])
                except ValueError:
                    continue
                d, m, y2 = r["Date"].split("/")
                euro_date = f"20{y2}-{m}-{d}" if len(y2) == 2 else r["Date"]
                home_raw, away_raw = r.get("HomeTeam", ""), r.get("AwayTeam", "")
                home = aligner.resolve(home_raw)
                away = aligner.resolve(away_raw)
                existing = db.scalar(select(MatchResult).where(
                    MatchResult.home == home, MatchResult.away == away,
                    MatchResult.match_date == euro_date))
                if existing:
                    continue
                db.add(MatchResult(source="football-data", league=cn_name,
                                   home_raw=home_raw, away_raw=away_raw,
                                   home=home, away=away, match_date=euro_date,
                                   goals_home=gh, goals_away=ga,
                                   retrieved_at=datetime.now(CN).isoformat(timespec="seconds")))
                db.flush()  # autoflush=False：下一季重扫时存在性检查可见
                total += 1
    db.commit()
    note = f"赛果 +{total}"
    if errors:
        note += f"（失败 {len(errors)}：{';'.join(errors[:3])}）"
    return total, note


def _outcome_1x2(gh: int, ga: int) -> str:
    return "主胜" if gh > ga else ("平局" if gh == ga else "客胜")


def _outcome_handicap(gh: int, ga: int, line_val: float) -> str:
    adj = gh - ga + line_val
    return "主胜" if adj > 0 else ("平局" if adj == 0 else "客胜")


def settle_verdicts(db: Session, trade_date: str | None = None) -> int:
    """对有 pick 且未结算的判决结算。返回结算条数。

    匹配规则：canonical 对阵 + 开赛 CN 日期 ∈ {euro_date, euro_date+1}
    （欧洲晚场 = 北京次日凌晨）。无赛果 → 保持未结算。
    """
    q = select(Verdict).where(Verdict.pick.isnot(None), Verdict.settled.is_(None))
    if trade_date:
        q = q.where(Verdict.trade_date == trade_date)
    verdicts = db.scalars(q).all()
    n = 0
    for v in verdicts:
        ko = datetime.strptime(v.kickoff, "%Y-%m-%d %H:%M:%S")
        cands = []
        for offset in (0, 1):
            euro_date = (ko - timedelta(days=offset)).strftime("%Y-%m-%d")
            cands.append(euro_date)
        result = None
        for ed in cands:
            result = db.scalar(select(MatchResult).where(
                MatchResult.home == v.home, MatchResult.away == v.away,
                MatchResult.match_date == ed))
            if result:
                break
        if result is None:
            continue
        if v.pool == "hhad" and v.goal_line:
            try:
                line_val = float(v.goal_line)
            except ValueError:
                line_val = 0.0
            actual = _outcome_handicap(result.goals_home, result.goals_away, line_val)
        else:
            actual = _outcome_1x2(result.goals_home, result.goals_away)
        v.settled = "win" if actual == v.pick.get("dir") else "lose"
        v.result_score = f"{result.goals_home}-{result.goals_away}"
        v.settled_at = utcnow()
        n += 1
    db.commit()
    return n


def ledger_stats(db: Session) -> dict:
    """公开账本统计：全部 promoted 判决的胜负与当前连败（连败公开是产品承诺）。"""
    rows = db.scalars(
        select(Verdict).where(Verdict.status == "promoted").order_by(Verdict.kickoff)
    ).all()
    settled = [v for v in rows if v.settled]
    wins = sum(1 for v in settled if v.settled == "win")
    streak = 0
    for v in reversed(settled):
        if v.settled == "lose":
            streak += 1
        else:
            break
    return {
        "promoted_total": len(rows),
        "settled": len(settled),
        "wins": wins,
        "losses": len(settled) - wins,
        "current_losing_streak": streak,
        "unsettled": len(rows) - len(settled),
    }
