#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sportmonks 深度探测 2：具体场次预测/赔率/价值投注/历史/语言/加购边界。"""
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import os
TOKEN = os.environ.get("SPORTMONKS_TOKEN") or Path(
    os.environ.get("SM_TOKEN_FILE", "C:/Users/26363/AppData/Local/Temp/sm_token.txt")
).read_text(encoding="utf-8").strip()
BASE = "https://api.sportmonks.com/v3/football"
OUT = Path(r"C:\Users\26363\AppData\Local\Temp\sm_probe")
OUT.mkdir(exist_ok=True)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path: str, params: str = "", label: str = "") -> dict:
    url = f"{BASE}{path}?api_token={TOKEN}"
    if params:
        url += "&" + params
    try:
        with OPENER.open(urllib.request.Request(url, headers={"Accept": "application/json",
                                                              "User-Agent": "qiuduoduo-probe"}), timeout=40) as r:
            data = json.loads(r.read().decode("utf-8"))
            left = r.headers.get("x-ratelimit-remaining")
        print(f"[OK] {label or path} left={left}")
        if label:
            (OUT / f"{label}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        print(f"[HTTP {e.code}] {label or path}: {body}")
        return {"_error": e.code}
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label or path}: {str(e)[:150]}")
        return {"_error": -1}


def main() -> None:
    # 1) 全部订阅联赛（分页计数）
    total, pages, ids = 0, 0, []
    url_path, params = "/leagues", "per_page=50"
    while True:
        d = get(url_path, params, label=f"leagues_p{pages+1}")
        if "_error" in d:
            break
        rows = d.get("data") or []
        total += len(rows)
        ids += [(r.get("id"), r.get("name")) for r in rows]
        pages += 1
        nxt = (d.get("pagination") or {}).get("next_page")
        if not nxt or pages >= 10:
            break
        q = urllib.parse.urlparse(nxt).query
        url_path = "/leagues"
        params = q.split("api_token=")[0].rstrip("&")
    print(f"subscription leagues: {total} (pages={pages})")
    wanted = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
              "Championship", "2. Bundesliga", "Ligue 2", "Eredivisie", "Eerste Divisie",
              "Primeira Liga", "J-League", "J2-League", "K League 1", "A-League",
              "Serie A", "Serie B", "Liga Profesional", "Major League Soccer", "Liga MX",
              "EFL Trophy", "UEFA Champions League", "UEFA Europa League",
              "UEFA Conference League", "UEFA Nations League", "Ybc Levain Cup"]
    have = {name for _, name in ids}
    for w in wanted:
        hit = [n for n in have if n and w.lower() in n.lower()]
        print(f"  {w}: {'YES ' + str(hit[:2]) if hit else 'NO'}")

    # 2) 具体场次预测（EFL Trophy / J-League Cup）
    for fid, tag in ((19809122, "pred_efl_19809122"), (19903103, "pred_jlc_19903103")):
        d = get(f"/predictions/probabilities/fixtures/{fid}", "include=type;metadata&per_page=100", label=tag)
        if "_error" not in d:
            rows = d.get("data") or []
            print(f"  fixture {fid}: prediction rows={len(rows)}")
            for r in rows[:12]:
                t = (r.get("type") or {}).get("name") or r.get("type_id")
                print("    ", r.get("type_id"), t, json.dumps(r.get("predictions"), ensure_ascii=False)[:110])
            for r in rows:
                if r.get("type_id") == 37072:
                    print("    PREDICTION_STATUS:", json.dumps(r.get("predictions"), ensure_ascii=False)[:200])

    # 3) Nations League 场次（11-12 UTC / 11-13 CN）
    d = get("/fixtures/date/2026-11-12", "include=participants;league&per_page=50", label="fixtures_20261112")
    n_ids = []
    if "_error" not in d:
        for r in d.get("data") or []:
            lg = (r.get("league") or {}).get("name") or ""
            if "Nations League" in lg:
                n_ids.append(r["id"])
                print(f"  NL fixture {r['id']}: {[p.get('name') for p in (r.get('participants') or [])]}")
    for fid in n_ids[:2]:
        dd = get(f"/predictions/probabilities/fixtures/{fid}", "include=type;metadata&per_page=100",
                 label=f"pred_nl_{fid}")
        if "_error" not in dd:
            print(f"  NL fixture {fid} prediction rows={len(dd.get('data') or [])}")

    # 4) 价值投注（正确路径尝试）
    for p in ("/predictions/value-bets", "/predictions/valuebets", "/predictions/value_bets"):
        d = get(p, "per_page=3", label="valuebets_try")
        if "_error" not in d:
            print(f"  valuebets path OK: {p} rows={len(d.get('data') or [])}")
            break

    # 5) 赔率（EFL Trophy 场次）
    d = get("/odds/pre-match/fixtures/19809122", "per_page=50", label="odds_efl_19809122")
    if "_error" not in d:
        rows = d.get("data") or []
        print(f"  odds rows={len(rows)}")
        bms = {}
        for r in rows:
            bm = r.get("bookmaker_id")
            bms[bm] = bms.get(bm, 0) + 1
        print("  bookmaker ids:", sorted(bms.items(), key=lambda x: -x[1])[:12])
        if rows:
            print("  sample odd:", json.dumps(rows[0], ensure_ascii=False)[:500])

    # 6) 书商字典（确认 Pinnacle id）
    for p in ("/odds/bookmakers", "/bookmakers"):
        d = get(p, "per_page=100", label="bookmakers")
        if "_error" not in d:
            for b in d.get("data") or []:
                if "pinnacle" in (b.get("name") or "").lower():
                    print("  PINNACLE:", b.get("id"), b.get("name"))
            break

    # 7) xG 加购边界
    get("/expected/teams/1", "per_page=3", label="xg_teams")

    # 8) 滚球预测（Advanced 试用）
    get("/predictions/live/probabilities", "per_page=3", label="live_pred")

    # 9) 中文
    d = get("/leagues/39", "locale=zh", label="zh_league")
    if "_error" not in d:
        print("  zh league name:", (d.get("data") or {}).get("name"))

    # 10) 历史预测：找 11-09 已结束场次
    d = get("/fixtures/date/2026-11-09", "include=participants;league;state&per_page=50", label="fixtures_20261109")
    if "_error" not in d:
        for r in d.get("data") or []:
            st = (r.get("state") or {}).get("name") or ""
            if "finished" in st.lower() or "ft" in st.lower():
                fid = r["id"]
                print(f"  finished fixture {fid}: {[p.get('name') for p in (r.get('participants') or [])]} state={st}")
                dd = get(f"/predictions/probabilities/fixtures/{fid}", "include=type&per_page=100",
                         label=f"pred_hist_{fid}")
                print("   historical prediction rows:", len(dd.get("data") or []) if "_error" not in dd else "ERR")
                break


if __name__ == "__main__":
    main()
