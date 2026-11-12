#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实回测：Sportmonks Prediction 1X2 vs Pinnacle 收盘（去水），2026-10 样本。"""
import csv
import json
import math
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import os
TOKEN = os.environ.get("SPORTMONKS_TOKEN") or Path(
    os.environ.get("SM_TOKEN_FILE", "C:/Users/26363/AppData/Local/Temp/sm_token.txt")
).read_text(encoding="utf-8").strip()
BASE = "https://api.sportmonks.com/v3/football"
OUT = Path(r"C:\Users\26363\AppData\Local\Temp\sm_backtest")
OUT.mkdir(exist_ok=True)
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CALLS = 0


def get(path: str, params: str = "") -> dict:
    global CALLS
    url = f"{BASE}{path}?api_token={TOKEN}" + ("&" + params if params else "")
    CALLS += 1
    for attempt in range(3):
        try:
            with OP.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5)
                continue
            return {"_error": e.code}
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return {"_error": -1}


LEAGUES = {8: "EPL", 564: "La Liga", 384: "Serie A", 9: "Championship",
           1022: "J2", 1034: "K League1", 39: "EFL Trophy", 72: "Eredivisie",
           74: "Eerste", 304: "Ligue 2", 648: "Brazil A", 651: "Serie B",
           779: "MLS", 1356: "A-League"}


def actual_result(fx: dict) -> str | None:
    goals = {"home": 0, "away": 0}
    current = {}
    part = {p["id"]: (p.get("meta") or {}).get("location") for p in (fx.get("participants") or [])}
    for s in fx.get("scores") or []:
        loc = (s.get("score") or {}).get("participant")
        g = (s.get("score") or {}).get("goals")
        if loc not in ("home", "away") or g is None:
            continue
        if s.get("description") == "CURRENT":
            current[loc] = g
        elif s.get("description") in ("1ST_HALF", "2ND_HALF"):
            goals[loc] += g
    h = current.get("home", goals["home"])
    a = current.get("away", goals["away"])
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def rps(probs: dict, outcome: str) -> float:
    order = ["home", "draw", "away"]
    onehot = [1.0 if o == outcome else 0.0 for o in order]
    s1 = probs["home"] - onehot[0]
    s2 = (probs["home"] + probs["draw"]) - (onehot[0] + onehot[1])
    return 0.5 * (s1 * s1 + s2 * s2)


def logloss(probs: dict, outcome: str) -> float:
    return -math.log(max(probs[outcome], 1e-6))


def main() -> None:
    rows = []
    coverage = {}
    d = date(2026, 10, 1)
    end = date(2026, 10, 31)
    while d <= end:
        day = d.isoformat()
        fx = get(f"/fixtures/date/{day}", "include=participants;scores;league;state&per_page=50")
        for f in fx.get("data") or []:
            lid = f.get("league_id")
            if lid not in LEAGUES:
                continue
            if (f.get("state") or {}).get("name") != "Full Time":
                continue
            lst = coverage.setdefault(lid, [])
            if len(lst) >= 12:
                continue
            lst.append(f)
        d += timedelta(days=1)

    for lid, fixtures in coverage.items():
        for f in fixtures:
            fid = f["id"]
            pred = get(f"/predictions/probabilities/fixtures/{fid}", "include=type&per_page=100")
            p_row = next((r for r in (pred.get("data") or []) if r.get("type_id") == 237), None)
            odds = get(f"/odds/pre-match/fixtures/{fid}",
                       "filters=markets:1;bookmakers:20&include=bookmaker&per_page=10")
            o_rows = odds.get("data") or []
            outcome = actual_result(f)
            if not p_row or len(o_rows) < 3 or outcome is None:
                continue
            sm = {k: v / 100.0 for k, v in p_row["predictions"].items()}
            pin = {}
            for o in o_rows:
                label = (o.get("label") or "").lower()
                pin[label] = float(o["value"])
            if set(pin) != {"home", "draw", "away"}:
                continue
            inv = {k: 1.0 / v for k, v in pin.items()}
            total = sum(inv.values())
            pin_p = {k: v / total for k, v in inv.items()}
            rows.append({
                "league": LEAGUES[lid], "fixture_id": fid,
                "outcome": outcome,
                "sm_home": round(sm["home"], 4), "sm_draw": round(sm["draw"], 4),
                "sm_away": round(sm["away"], 4),
                "pin_home": round(pin_p["home"], 4), "pin_draw": round(pin_p["draw"], 4),
                "pin_away": round(pin_p["away"], 4),
                "sm_logloss": round(logloss(sm, outcome), 4),
                "pin_logloss": round(logloss(pin_p, outcome), 4),
                "sm_rps": round(rps(sm, outcome), 4),
                "pin_rps": round(rps(pin_p, outcome), 4),
                "sm_hit": int(max(sm, key=sm.get) == outcome),
                "pin_hit": int(max(pin_p, key=pin_p.get) == outcome),
            })

    with open(OUT / "backtest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    print(f"calls={CALLS} samples={len(rows)}\n")
    print(f"{'league':<12}{'n':>4}{'SM ll':>8}{'Pin ll':>8}{'SM RPS':>8}{'Pin RPS':>8}{'SM hit':>8}{'Pin hit':>8}")
    for lid, name in LEAGUES.items():
        sub = [r for r in rows if r["league"] == name]
        if not sub:
            continue
        n = len(sub)
        avg = lambda k: sum(r[k] for r in sub) / n  # noqa: E731
        print(f"{name:<12}{n:>4}{avg('sm_logloss'):>8.3f}{avg('pin_logloss'):>8.3f}"
              f"{avg('sm_rps'):>8.3f}{avg('pin_rps'):>8.3f}"
              f"{avg('sm_hit'):>8.2f}{avg('pin_hit'):>8.2f}")
    if rows:
        n = len(rows)
        avg = lambda k: sum(r[k] for r in rows) / n  # noqa: E731
        print(f"{'ALL':<12}{n:>4}{avg('sm_logloss'):>8.3f}{avg('pin_logloss'):>8.3f}"
              f"{avg('sm_rps'):>8.3f}{avg('pin_rps'):>8.3f}"
              f"{avg('sm_hit'):>8.2f}{avg('pin_hit'):>8.2f}")
    (OUT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
