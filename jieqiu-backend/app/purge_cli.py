"""CLI：python -m app.purge_cli —— 清除注销期满（7 天）的用户数据。"""
from __future__ import annotations

import sys

from .db import SessionLocal, init_db
from .modules.users import purge_expired_deletions


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        counts = purge_expired_deletions(db, days=7)
        print(f"[purge] {counts}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
