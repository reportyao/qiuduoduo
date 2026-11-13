"""Sportmonks 同步 CLI：
    python -m app.sportmonks_cli sync --date 2026-11-11
    python -m app.sportmonks_cli results --days 2
    python -m app.sportmonks_cli board
"""
from __future__ import annotations

import argparse

from .db import SessionLocal, init_db
from .features.board import service as board_service
from .modules.sportmonks import sync_trade_date
from .modules.sportmonks_results import backfill_verdict_results, sync_results
from .modules.timeutil import trade_date_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command",
                        choices=("sync", "results", "backfill", "live",
                                 "freeze", "enrich", "settle", "board"))
    parser.add_argument("--date", default=None)
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        if args.command == "backfill":
            result = backfill_verdict_results(db, days=max(args.days, 7))
        elif args.command == "results":
            result = sync_results(db, days=args.days)
        elif args.command == "live":
            result = {"ok": True,
                      "detail": board_service.sync_live_states(db, force=args.force)}
        elif args.command == "freeze":
            result = board_service.freeze_prediction_snapshots(db)
        elif args.command == "enrich":
            result = board_service.enrich_result_details(db, days=args.days)
        elif args.command == "settle":
            result = board_service.settle_prediction_snapshots(db)
        elif args.command == "board":
            result = {
                "ok": True,
                "live": board_service.sync_live_states(db, force=args.force),
                "enrich": board_service.enrich_result_details(db, days=args.days),
                "freeze": board_service.freeze_prediction_snapshots(db),
                "settle": board_service.settle_prediction_snapshots(db),
            }
        else:
            result = sync_trade_date(db, args.date or trade_date_now())
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
