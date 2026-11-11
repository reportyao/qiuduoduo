#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sportmonks 深度探测 5：xG 实际返回/订阅详情/书商过滤/历史深度/Pinnacle 覆盖。"""
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
    # 1) xG 实际返回
    d = json.loads((OUT / "p4_xg.json").read_text(encoding="utf-8")) if (OUT / "p4_xg.json").exists() else {}
    print("xG /expected/fixtures rows:", len(d.get("data") or []),
          "| sample:", json.dumps((d.get("data") or [None])[0], ensure_ascii=False)[:300])

    # 2) 订阅详情全文
    lg = json.loads((OUT / "leagues_p1.json").read_text(encoding="utf-8"))
    print("\nsubscription full:", json.dumps(lg.get("subscription"), ensure_ascii=False)[:900])

    # 3) 书商过滤变体（EFL Trophy Match Winner）
    fid = 19809122
    for params in ("filters=markets:1;bookmakers:20&include=bookmaker&per_page=10",
                   "filters=markets:1;bookmakerIds:20&include=bookmaker&per_page=10",
                   "filters=markets:1&include=bookmaker&per_page=100"):
        d = get(f"/odds/pre-match/fixtures/{fid}", params, label="p5_odds_filter")
        if "_error" not in d:
            rows = d.get("data") or []
            bms = {r.get("bookmaker_id") for r in rows}
            print(f"  [{params}] rows={len(rows)} bookmakers={sorted(bms)[:8]}")
            if len(bms) <= 2:
                print("   sample:", json.dumps(rows[:3], ensure_ascii=False)[:400])
                break

    # 4) Pinnacle 对日联杯的覆盖
    d = get("/odds/pre-match/fixtures/19903103", "filters=markets:1&include=bookmaker&per_page=100",
            label="p5_odds_jlc_mw")
    if "_error" not in d:
        rows = d.get("data") or []
        bms = {}
        for r in rows:
            bm = r.get("bookmaker") or {}
            bms.setdefault(bm.get("id"), bm.get("name"))
        print("  JLC Match Winner rows:", len(rows), "| bookmakers:", len(bms),
              "| pinnacle:", [(k, v) for k, v in bms.items() if "pinnacle" in (v or "").lower()])

    # 5) 历史预测深度（9 月/10 月/去年）
    for date in ("2026-09-19", "2026-10-17", "2025-11-08"):
        d = get(f"/fixtures/date/{date}", "include=participants;league;state&per_page=50",
                label=f"p5_fx_{date}")
        if "_error" in d:
            continue
        fids = [(r["id"], (r.get("league") or {}).get("name"),
                 [p.get("name") for p in (r.get("participants") or [])]) for r in (d.get("data") or [])]
        print(f"  {date}: fixtures={len(fids)} sample={fids[:2]}")
        if fids:
            dd = get(f"/predictions/probabilities/fixtures/{fids[0][0]}", "include=type&per_page=10",
                     label=f"p5_pred_{date}")
            print(f"   predictions rows for {fids[0][0]}:",
                  len(dd.get("data") or []) if "_error" not in dd else "ERR")

    # 6) 欧国联是否真的不在订阅（11-12 UTC 场次）
    d = json.loads((OUT / "fixtures_20261112.json").read_text(encoding="utf-8"))
    names = [(r.get("league") or {}).get("name") for r in (d.get("data") or [])]
    print("\nfixtures 11-12 leagues:", sorted(set(names)))
    print("Nations League present:", any("Nations" in (n or "") for n in names))


if __name__ == "__main__":
    main()
