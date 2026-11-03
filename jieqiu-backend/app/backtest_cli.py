"""CLI：python -m app.backtest [label] —— 跑最近一个完整赛季校准回测并存库。"""
from __future__ import annotations

import sys

from .db import SessionLocal, init_db
from .modules.backtest import run_and_store


def main() -> int:
    init_db()
    label = sys.argv[1] if len(sys.argv) > 1 else "dc-v1.1-epl-2024h1"
    db = SessionLocal()
    try:
        ev = run_and_store(db, label, "2024-01-01", "2024-06-30",
                           halflife_days=180, window_days=540, rho=-0.06, min_matches=3)
        m = ev.metrics
        print(f"[eval] {label}: n={m['n']} logloss={m['logloss']} accuracy={m['accuracy']}")
        for c in m["calibration"]:
            print(f"  {c['bucket']:>9} n={c['n']:>3} pred={c['mean_predicted']:.3f} obs={c['observed_freq']:.3f}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
