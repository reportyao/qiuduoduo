"""推荐主链 CLI：build → review → publish → expire。

    python -m app.recommendations_cli run --date 2026-11-05
"""
from __future__ import annotations

import argparse
import json

from .db import SessionLocal, init_db
from .features.recommendations import service


def main() -> None:
    ap = argparse.ArgumentParser(description="recommendation pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--date", default=None)
    run.add_argument("--stake", type=float, default=100)
    args = ap.parse_args()
    init_db()
    db = SessionLocal()
    try:
        out = service.run_pipeline(db, date=args.date, stake=args.stake)
    finally:
        db.close()
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
