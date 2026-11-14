"""SQLite 在线备份 CLI：每日 cron 调用。

- `sqlite3.Connection.backup()` 在线一致性备份（WAL 安全，不锁 API 写入）；
- 日备滚动保留 N 份；周日的那份同时归档 weekly，保留 N 周；
- OPC：job_start/finish 写 ops_jobs，失败进 ops_exception。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import utcnow  # noqa: E402


def _prune(pattern: str, keep: int, out_dir: Path) -> list[str]:
    files = sorted(out_dir.glob(pattern))
    removed = []
    for old in files[:-keep] if keep > 0 else files:
        try:
            old.unlink()
            removed.append(old.name)
        except OSError:
            pass
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="SQLite 在线备份 + 滚动保留")
    ap.add_argument("--keep", type=int, default=7, help="日备保留份数")
    ap.add_argument("--weekly-keep", type=int, default=4, help="周备保留份数")
    ap.add_argument("--db", default="", help="源库路径；缺省取 JQ_DATABASE_URL")
    ap.add_argument("--out-dir", default="", help="备份输出目录；缺省 JQ_BACKUP_DIR 或 ~/backups")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db_url = args.db or os.environ.get("JQ_DATABASE_URL", "")
    db_path = db_url.removeprefix("sqlite:///") if db_url.startswith("sqlite:///") else db_url
    if not db_path or not Path(db_path).is_file():
        print(json.dumps({"ok": False, "error": f"数据库不存在: {db_path or '(空)'}"},
                         ensure_ascii=False))
        return 2
    home = Path.home()
    out_dir = Path(args.out_dir or os.environ.get("JQ_BACKUP_DIR", str(home / "backups")))
    out_dir.mkdir(parents=True, exist_ok=True)

    from app.db import SessionLocal
    from app.modules import ops
    db = SessionLocal()
    job_id = ops.job_start(db, "db_backup")
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        tmp_path = out_dir / f".db-backup-{stamp}.tmp"
        final_path = out_dir / f"db-backup-{stamp}.db"
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp_path)
        src.backup(dst)
        dst.close()
        src.close()
        tmp_path.replace(final_path)

        removed_daily = _prune("db-backup-*.db", max(args.keep, 1), out_dir)
        removed_weekly: list[str] = []
        is_sunday = datetime.now(timezone.utc).weekday() == 6
        weekly_name = f"db-weekly-{stamp}.db"
        weekly_path = out_dir / weekly_name
        if is_sunday:
            weekly_path.write_bytes(final_path.read_bytes())
            removed_weekly = _prune("db-weekly-*.db", max(args.weekly_keep, 1), out_dir)
        ops.job_finish(db, job_id, "ok")
        payload = {"ok": True, "backup": final_path.name,
                   "size_bytes": final_path.stat().st_size,
                   "removed_daily": removed_daily,
                   "removed_weekly": removed_weekly, "weekly": is_sunday}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"[db-backup] {final_path.name} "
                  f"({payload['size_bytes'] // 1024}KB) 日备滚动删 {len(removed_daily)}"
                  f"{' · 周备已归档' if is_sunday else ''}")
        return 0
    except Exception as exc:
        db.rollback()
        ops.job_finish(db, job_id, "error", f"{type(exc).__name__}: {exc}")
        ops.exception(db, "db_backup_error", f"{type(exc).__name__}: {exc}",
                      severity=3, source="db_backup", dedupe_key="db_backup_error")
        print(json.dumps({"ok": False, "error": str(exc)[:300]}, ensure_ascii=False))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
