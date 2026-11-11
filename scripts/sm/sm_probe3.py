#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sportmonks 深度探测 3：预测类型结构/历史预测/赔率书商与市场/xG 路径。"""
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
        print(f"[HTTP {e.code}] {label or path}: {e.read().decode('utf-8','ignore')[:250]}")
        return {"_error": e.code}
    except Exception as e:  # noqa: BLE001
        print(f"[ERR] {label or path}: {str(e)[:150]}")
        return {"_error": -1}


def show_predictions(fid: int, tag: str) -> None:
    d = get(f"/predictions/probabilities/fixtures/{fid}", "include=type&per_page=100", label=tag)
    if "_error" in d:
        return
    rows = d.get("data") or []
    print(f"  fixture {fid}: rows={len(rows)}")
    for r in rows:
        t = (r.get("type") or {}).get("name") or ""
        print(f"    type={r.get('type_id'):>5} {t:<34} {json.dumps(r.get('predictions'), ensure_ascii=False)[:100]}")


def main() -> None:
    for fid, tag in ((19809122, "p3_pred_efl"), (19903103, "p3_pred_jlc"),
                     (19667064, "p3_pred_serieb")):
        show_predictions(fid, tag)

    # 历史预测（已完赛 La Liga 2）
    show_predictions(19744991, "p3_pred_hist")

    # 赔率 + 书商/市场 include
    d = get("/odds/pre-match/fixtures/19809122",
            "include=bookmaker;market&per_page=5", label="p3_odds_include")
    if "_error" not in d:
        for r in (d.get("data") or [])[:5]:
            bm = r.get("bookmaker") or {}
            mk = r.get("market") or {}
            print(f"  bm={bm.get('id')} {bm.get('name')} | market={mk.get('id')} {mk.get('name')}"
                  f" | label={r.get('label')} value={r.get('value')}")

    # 只拉 Pinnacle 的赔率（假设书商名可查后再定 id；先按 1X2 市场过滤试探）
    for params in ("filters=bookmakerIds:2&per_page=5",
                   "filters=marketIds:1&per_page=5",
                   "filters=bookmakerIds:2;marketIds:1&per_page=5"):
        d = get("/odds/pre-match/fixtures/19809122", params, label="p3_odds_filter")
        if "_error" not in d:
            print(f"  filter [{params}] rows={len(d.get('data') or [])}")

    # xG 文档给出的真实路径
    xg = get("/expected/team/1", "per_page=2", label="p3_xg_team")
    xg2 = get("/expected/teams", "per_page=2", label="p3_xg_teams")

    # 场次 has_odds / 21 天窗口
    d = get("/fixtures/19809122", "include=participants;league;state", label="p3_fixture_detail")
    if "_error" not in d:
        fx = d.get("data") or {}
        print("  has_odds:", fx.get("has_odds"), "| starting:", fx.get("starting_at"),
              "| state:", (fx.get("state") or {}).get("name"))

    # 未来 21 天外的预测（验证窗口边界）
    get("/predictions/probabilities/fixtures/19903103", "", label="p3_pred_noparam")


if __name__ == "__main__":
    main()
