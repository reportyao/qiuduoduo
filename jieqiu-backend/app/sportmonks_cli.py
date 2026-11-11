"""Sportmonks 同步 CLI：
    python -m app.sportmonks_cli sync --date 2026-11-11
    python -m app.sportmonks_cli results --days 2
"""
from __future__ import annotations

import argparse

from .db import SessionLocal, init_db
from .modules.sportmonks import sync_trade_date
from .modules.sportmonks_results import backfill_verdict_results, sync_results
from .modules.timeutil import trade_date_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "results", "backfill"))
    parser.add_argument("--date", default=None)
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        if args.command == "backfill":
            result = backfill_verdict_results(db, days=max(args.days, 7))
        elif args.command == "results":
            result = sync_results(db, days=args.days)
        else:
            result = sync_trade_date(db, args.date or trade_date_now())
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
