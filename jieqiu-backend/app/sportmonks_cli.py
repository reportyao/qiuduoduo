"""Sportmonks 同步 CLI：python -m app.sportmonks_cli sync --date 2026-11-11"""
from __future__ import annotations

import argparse

from .db import SessionLocal, init_db
from .modules.sportmonks import sync_trade_date
from .modules.timeutil import trade_date_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync",))
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        result = sync_trade_date(db, args.date or trade_date_now())
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
