#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计最近 N 天竞彩足球每日卡片的联赛分布（数据源：500 网竞彩页联赛过滤器）。"""
import json
import re
import time
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0",
        "Referer": "https://live.500.com/"}
ROW = re.compile(
    r'check_league\[\]" value="\d*" checked="checked"\s*/>\s*'
    r'<span class="team"[^>]*>([^<]+)</span>\[?(\d*)\]?')


def fetch_day(day: str) -> dict[str, int]:
    url = f"https://live.500.com/jczq.php?e={day}"
    with OPENER.open(urllib.request.Request(url, headers=HDRS), timeout=30) as r:
        txt = r.read().decode("gbk", "ignore")
    found: dict[str, int] = {}
    for m in ROW.finditer(txt):
        league = m.group(1).strip()
        count = int(m.group(2) or 0)
        if league:
            found[league] = found.get(league, 0) + count
    return found


def main() -> None:
    start = date(2026, 9, 9)
    end = date(2026, 11, 9)
    totals: dict[str, int] = defaultdict(int)
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    days = 0
    empty_days = []
    cur = start
    while cur <= end:
        day = cur.isoformat()
        try:
            found = fetch_day(day)
        except Exception as exc:  # noqa: BLE001 - 单日失败不影响整体
            print(f"[warn] {day} 抓取失败: {exc}")
            time.sleep(2)
            cur += timedelta(days=1)
            continue
        if found:
            days += 1
            month = day[:7]
            for league, count in found.items():
                totals[league] += count
                by_month[month][league] += count
        else:
            empty_days.append(day)
        time.sleep(0.4)
        cur += timedelta(days=1)
    print(f"有效天数 {days}，无比赛日 {len(empty_days)}: {empty_days}")
    print("\n== 最近两个月联赛总场次 TOP25 ==")
    for league, count in sorted(totals.items(), key=lambda x: -x[1])[:25]:
        print(f"{league}\t{count}")
    out = {"totals": totals, "by_month": {k: dict(v) for k, v in by_month.items()}}
    with open("jczq_leagues_2m.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n已写 jczq_leagues_2m.json")


if __name__ == "__main__":
    main()
