"""国际盘供给 CLI：诊断为什么市闸过不了 / 手动触发一次同步。

用法：
  python -m app.odds_cli status [--json]
  python -m app.odds_cli sync [--json]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .db import SessionLocal
from .modules.align import Aligner, seed_aliases
from .modules.intl_odds import sync_the_odds_api
from .modules.supply import content_supply


def _status(as_json: bool) -> int:
    db = SessionLocal()
    try:
        data = content_supply(db)
        if as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            intl = data["intl_odds"]
            print(f"日期 {data['date']}｜场次 {data['matches']}｜判决 {data['verdicts']['total']}"
                  f"｜promoted {data['verdicts']['promoted']}｜published {data['published']}")
            print(f"国际盘：配置={intl['configured']} 总行数={intl['total']}"
                  f" 覆盖场次={intl['covered_matches']}/{data['matches']}")
            print(f"市闸：pass={data['market_gate']['pass']} fail={data['market_gate']['fail']}"
                  f" pending={data['market_gate']['pending_data']}")
            if data["blocked_reason"]:
                print(f"阻塞原因：{data['blocked_reason']}")
            if not intl["configured"]:
                print("提示：设置 JQ_ODDS_API_KEY 后运行 `python -m app.odds_cli sync`。")
        return 0 if data["published"] or data["verdicts"]["promoted"] else 1
    finally:
        db.close()


def _sync(as_json: bool) -> int:
    db = SessionLocal()
    try:
        seed_aliases(db)
        n, note = sync_the_odds_api(db, Aligner(db), datetime.now(timezone.utc))
        if as_json:
            print(json.dumps({"synced": n, "note": note}, ensure_ascii=False))
        else:
            print(f"同步 {n} 场：{note}")
        return 0 if n else 2
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="球多多国际盘供给诊断/同步")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status", help="查看当日内容供给漏斗")
    p_status.add_argument("--json", action="store_true")
    p_sync = sub.add_parser("sync", help="手动同步一次 The Odds API")
    p_sync.add_argument("--json", action="store_true")
    args = parser.parse_args()
    raise SystemExit(_status(args.json) if args.cmd == "status" else _sync(args.json))


if __name__ == "__main__":
    main()
