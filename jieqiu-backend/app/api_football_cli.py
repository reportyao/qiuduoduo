"""API-Football 同步 CLI。

用法：
    python -m app.api_football_cli status --json
    python -m app.api_football_cli sync --date 2026-11-04
    python -m app.api_football_cli link --fixture 12345 --match 2042508
"""
from __future__ import annotations

import argparse
import json

from .db import SessionLocal
from .modules import api_football


def main() -> None:
    parser = argparse.ArgumentParser(description="API-Football sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--date", default=None)
    p_sync.add_argument("--next-day", action="store_true")
    p_sync.add_argument("--json", action="store_true")
    p_enrich = sub.add_parser("sync-enrich")
    p_enrich.add_argument("--lineups-max", type=int, default=2)
    p_enrich.add_argument("--injuries-max", type=int, default=1)
    p_enrich.add_argument("--json", action="store_true")
    p_link = sub.add_parser("link")
    p_link.add_argument("--fixture", type=int, required=True)
    p_link.add_argument("--match", required=True)
    p_link.add_argument("--json", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "status":
            out = api_football.status(db)
        elif args.cmd == "sync":
            out = api_football.sync_all(db, date=args.date, include_next_day=args.next_day)
        elif args.cmd == "sync-enrich":
            out = api_football.sync_enrich(
                db, lineups_max=args.lineups_max, injuries_max=args.injuries_max)
        else:
            out = api_football.link_fixture(db, args.fixture, args.match)
    except api_football.ApiFootballError as exc:
        out = {"ok": False, "error": str(exc)}
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, sort_keys=True) if getattr(args, "json", False) else out)


if __name__ == "__main__":
    main()
