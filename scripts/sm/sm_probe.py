#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sportmonks 真实数据探测：鉴权、订阅范围、预测覆盖、赔率、加购边界。"""
import json
import sys
import urllib.error
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
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "qiuduoduo-probe"})
    try:
        with OPENER.open(req, timeout=40) as r:
            data = json.loads(r.read().decode("utf-8"))
            hdrs = {k.lower(): v for k, v in r.headers.items()}
        print(f"[OK] {label or path} status=200 rate_left={hdrs.get('x-ratelimit-remaining')} "
              f"rate_limit={hdrs.get('x-ratelimit-limit')}")
        if label:
            (OUT / f"{label}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:400]
        print(f"[HTTP {e.code}] {label or path}: {body}")
        return {"_error": e.code, "_body": body}
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label or path}: {str(e)[:200]}")
        return {"_error": -1, "_body": str(e)}


def main() -> None:
    # 1) 订阅范围：my/leagues 或 leagues
    for p in ("/my/leagues", "/leagues"):
        d = get(p, "per_page=5", label="my_leagues" if p == "/leagues" else "my_leagues")
        if "_error" not in d:
            print("   keys:", list(d.keys()), "| count:", len(d.get("data") or []))
            break

    # 2) 预测总览（订阅内全部概率）
    d = get("/predictions/probabilities", "per_page=3", label="predictions_all")
    if "_error" not in d:
        data = d.get("data") or []
        print("   predictions rows:", len(data))
        if data:
            row = data[0]
            print("   sample row keys:", list(row.keys()))
            print("   sample:", json.dumps(row, ensure_ascii=False)[:600])

    # 3) 价值投注
    d = get("/predictions/valuebets", "per_page=3", label="valuebets")
    if "_error" not in d:
        print("   valuebets rows:", len(d.get("data") or []))

    # 4) 联赛搜索：EFL Trophy / Nations League / Levain
    for q in ("EFL Trophy", "Nations League", "Levain"):
        d = get("/leagues/search/" + urllib.parse.quote(q), "per_page=5", label=f"league_{q.replace(' ', '_')}")
        if "_error" not in d:
            for row in (d.get("data") or [])[:5]:
                print(f"   {q}: id={row.get('id')} name={row.get('name')} country={row.get('country_id')}")

    # 5) 可预测性（EFL Trophy #39 / Nations League #1538）
    for lid in (39, 1538):
        d = get(f"/predictions/predictability/leagues/{lid}", "per_page=50", label=f"predictability_{lid}")
        if "_error" not in d:
            rows = d.get("data") or []
            print(f"   league {lid}: rows={len(rows)}")
            for r in rows[:6]:
                print("    ", r.get("type_id"), json.dumps(r.get("data"), ensure_ascii=False)[:160])

    # 6) 11-11 赛程（含联赛/参赛方/状态）
    d = get("/fixtures/date/2026-11-11", "include=participants;league;state;venue&per_page=50",
            label="fixtures_20261111")
    if "_error" not in d:
        rows = d.get("data") or []
        print("   fixtures on 2026-11-11:", len(rows))
        for r in rows[:10]:
            league = (r.get("league") or {}).get("name")
            parts = [p.get("name") for p in (r.get("participants") or [])]
            print(f"    id={r.get('id')} {league} {parts} state={r.get('state_id')} "
                  f"starting={r.get('starting_at')}")
    print("\nraw responses ->", OUT)


if __name__ == "__main__":
    import urllib.parse  # noqa: F401
    main()
