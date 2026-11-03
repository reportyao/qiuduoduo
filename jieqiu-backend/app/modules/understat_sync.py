"""Understat 本季 xG 同步（可插拔源）。

网络可达时增量抓取 2025-26 / 2026-27 五大联赛 → 原始 dump 落到 xg_extra_dir；
不可达（SSL EOF / 超时）→ 跳过并说明，管线不中断。12h 节流。
dc_model._load_xg 会合并主 csv + dumps 目录，数据一到位模闸自动复活。
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

from ..config import get_settings

LEAGUES = {
    "ENG Premier League": "EPL",
    "ESP La Liga": "La_Liga",
    "DEU Bundesliga 1": "Bundesliga",
    "ITA Serie A": "Serie_A",
    "FRA Ligue 1": "Ligue_1",
}
SEASONS = ("2025-2026", "2026-2027")
_THROTTLE_FILE = os.path.join(tempfile.gettempdir(), "jq_understat_last_sync")


def _throttled(now: datetime) -> bool:
    st = get_settings()
    try:
        if os.path.exists(_THROTTLE_FILE):
            last = datetime.fromisoformat(open(_THROTTLE_FILE).read().strip())
            if (now - last).total_seconds() < st.odds_sync_min_interval_hours * 3600:
                return True
    except Exception:
        pass
    return False


def _mark(now: datetime) -> None:
    try:
        with open(_THROTTLE_FILE, "w") as f:
            f.write(now.isoformat())
    except Exception:
        pass


def sync_understat(now: datetime | None = None, fetcher=None) -> tuple[int, str]:
    """返回 (成功写入的联赛-季数量, 说明)。fetcher(league_full, season) -> DataFrame。"""
    st = get_settings()
    now = now or datetime.now(timezone.utc)
    out_dir = getattr(st, "xg_extra_dir", "") or os.path.join(
        os.path.dirname(st.xg_data_path or "."), "xg_dumps")
    os.makedirs(out_dir, exist_ok=True)

    if _throttled(now):
        return 0, "节流：距上次尝试不足间隔，跳过"

    if fetcher is None:
        def fetcher(league_full: str, season: str):
            from penaltyblog.scrapers import Understat
            return Understat(league_full, season).get_fixtures()

    ok = 0
    notes = []
    for league_full, tag in LEAGUES.items():
        for season in SEASONS:
            path = os.path.join(out_dir, f"understat_{tag}_{season.replace('-', '_')}.csv")
            if os.path.exists(path) and os.path.getsize(path) > 2000:
                continue  # 已有增量
            try:
                df = fetcher(league_full, season)
                if df is None or len(df) == 0:
                    continue
                df.to_csv(path, index=False)
                ok += 1
                notes.append(f"{tag}/{season}:{len(df)}")
            except Exception as e:
                notes.append(f"{tag}/{season}: {type(e).__name__}")
    _mark(now)
    if ok == 0:
        return 0, "xG 源不可达（" + "; ".join(notes[:3]) + "…）—— 模闸 pending，待出口恢复自动生效"
    return ok, "新落档 " + "; ".join(notes)
