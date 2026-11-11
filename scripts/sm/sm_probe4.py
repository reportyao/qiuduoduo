#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sportmonks 深度探测 4：市场过滤/Pinnacle/价值投注/历史深度/联赛模型质量。"""
import json
import urllib.error
import urllib.request
from pathlib import Path

import os
TOKEN = os.environ.get("SPORTMONKS_TOKEN") or Path(
    os.environ.get("SM_TOKEN_FILE", "C:/Users/26363/AppData/Local/Temp/sm_token.txt")
).read_text(encoding="utf-8").strip()
BASE = "https://api.sportmonks.com/v3/football"
OUT = Path(r"C:\Users\26363\AppData\Local\Temp\sm_probe")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path: str, params: str = "", label: str = "") -> dict:
    url = f"{BASE}{path}?api_token={TOKEN}"
    if params:
        url += "&" + params
    try:
        with OPENER.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=40) as r:
            data = json.loads(r.read().decode("utf-8"))
            left = r.headers.get("x-ratelimit-remaining")
        print(f"[OK] {label or path} left={left}")
        if label:
            (OUT / f"{label}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {label or path}: {e.read().decode('utf-8','ignore')[:220]}")
        return {"_error": e.code}
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label or path}: {str(e)[:150]}")
        return {"_error": -1}


def main() -> None:
    fid = 19809122  # EFL Trophy

    # 1) 市场过滤：只取 Match Winner(1)
    d = get(f"/odds/pre-match/fixtures/{fid}", "filters=markets:1&include=bookmaker;market&per_page=50",
            label="p4_odds_mw")
    if "_error" not in d:
        rows = d.get("data") or []
        print("  Match Winner rows:", len(rows))
        seen = {}
        for r in rows:
            bm = r.get("bookmaker") or {}
            seen.setdefault(bm.get("id"), bm.get("name"))
        print("  bookmakers:", json.dumps(seen, ensure_ascii=False))
        pin = [(k, v) for k, v in seen.items() if "pinnacle" in (v or "").lower()]
        print("  PINNACLE:", pin)
        for r in rows[:6]:
            print(f"    bm={r.get('bookmaker_id')} {r.get('label')} {r.get('value')} "
                  f"mkt={r.get('market_description')} update={r.get('latest_bookmaker_update')}")

    # 2) 价值投注（单场）
    d = get(f"/predictions/value-bets/fixtures/{fid}", "per_page=50", label="p4_valuebets_fixture")
    if "_error" not in d:
        rows = d.get("data") or []
        print("  valuebets rows:", len(rows))
        for r in rows[:5]:
            print("   ", json.dumps(r, ensure_ascii=False)[:200])

    # 3) 历史预测深度：2026-08-15 英超
    d = get("/fixtures/date/2026-08-15", "include=participants;league;state&per_page=50",
            label="p4_fixtures_20260815")
    old_fid = None
    if "_error" not in d:
        for r in d.get("data") or []:
            lg = (r.get("league") or {}).get("name") or ""
            if "Premier League" in lg:
                old_fid = r["id"]
                print("  old EPL fixture:", old_fid,
                      [p.get("name") for p in (r.get("participants") or [])],
                      (r.get("state") or {}).get("name"))
                break
    if old_fid:
        dd = get(f"/predictions/probabilities/fixtures/{old_fid}", "include=type&per_page=50",
                 label="p4_pred_old")
        print("  historical prediction rows (Aug):",
              len(dd.get("data") or []) if "_error" not in dd else "ERR")
        od = get(f"/odds/pre-match/fixtures/{old_fid}", "filters=markets:1&per_page=5",
                 label="p4_odds_old")
        print("  historical odds rows (Aug):",
              len(od.get("data") or []) if "_error" not in od else "ERR")

    # 4) 联赛模型质量对照（type 241/242/243）
    leagues = {8: "EPL", 564: "La Liga", 384: "Serie A", 82: "Bundesliga", 301: "Ligue 1",
               9: "Championship", 39: "EFL Trophy", 72: "Eredivisie", 74: "Eerste",
               1100: "Primeira", 1034: "K League1", 1022: "J2", 1031: "JLC",
               1356: "A-League", 779: "MLS", 636: "Argentina", 648: "Brazil A",
               651: "Serie B", 304: "Ligue 2", 567: "La Liga 2"}
    print("\n  league | 1X2 logloss(241) | hit(242) | rating(243) | trend(244)")
    for lid, name in leagues.items():
        dd = get(f"/predictions/predictability/leagues/{lid}", "per_page=50",
                 label=f"p4_predtab_{lid}")
        if "_error" in dd:
            continue
        vals = {}
        for r in dd.get("data") or []:
            if r.get("type_id") in (241, 242, 243, 244):
                vals[r["type_id"]] = (r.get("data") or {}).get("fulltime_result")
        print(f"  {name:<10} | {vals.get(241)} | {vals.get(242)} | {vals.get(243)} | {vals.get(244)}")

    # 5) xG 加购边界（正确路径）
    get("/expected/fixtures", "per_page=2", label="p4_xg")


if __name__ == "__main__":
    main()
