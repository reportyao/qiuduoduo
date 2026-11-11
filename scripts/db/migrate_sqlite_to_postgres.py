#!/usr/bin/env python3
"""SQLite → PostgreSQL 一次性数据迁移（schema 由 Alembic 建）。

用法（在 jieqiu-backend 目录）：
  python scripts/db/migrate_sqlite_to_postgres.py \
    --source sqlite:////home/ubuntu/jieqiu-data/jieqiu.db \
    --target postgresql+psycopg2://user:pass@host:5432/jieqiu \
    --dry-run

切库前必须：
1) 备份 SQLite；
2) 在目标空库 `alembic upgrade head`；
3) 先 `--dry-run` 核对每表行数；
4) 去掉 --dry-run 正式导入；
5) 切换 JQ_DATABASE_URL，跑 /health、/stream、worker --once；
6) 保留 SQLite 一个 release 周期用于回滚。

--force 会先 TRUNCATE 目标库全部表（仅用于演练库），生产禁止使用。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jieqiu-backend"))

from app.db import Base  # noqa: E402
from app import models  # noqa: F401,E402


def _engine(url: str):
    if url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool
        return create_engine(url, poolclass=NullPool)
    return create_engine(url, pool_pre_ping=True)


def _tables():
    return [t for t in Base.metadata.sorted_tables if t.name != "alembic_version"]


def _duplicate_check(conn, table_name: str, column: str) -> None:
    table = Base.metadata.tables.get(table_name)
    if table is None or column not in table.c:
        return
    col = table.c[column]
    rows = conn.execute(
        select(col, func.count()).where(col.isnot(None)).group_by(col)
        .having(func.count() > 1).limit(10)
    ).all()
    if rows:
        shown = ", ".join(f"{value!r}×{count}" for value, count in rows)
        raise SystemExit(f"{table_name}.{column} 有重复值，先人工归并：{shown}")


def _source_counts(conn) -> dict[str, int]:
    out = {}
    for table in _tables():
        try:
            out[table.name] = int(conn.scalar(select(func.count()).select_from(table)) or 0)
        except SQLAlchemyError:
            out[table.name] = 0  # 旧 SQLite 可能还没建这张表
    return out


def _target_counts(conn) -> dict[str, int]:
    out = {}
    for table in _tables():
        try:
            out[table.name] = int(conn.scalar(select(func.count()).select_from(table)) or 0)
        except SQLAlchemyError as exc:
            raise SystemExit(f"目标库缺表 {table.name}：先跑 alembic upgrade head（{exc}）")
    return out


def _copy(source, target, batch: int) -> dict[str, int]:
    copied = {}
    with source.connect() as sdst, target.begin() as tdst:
        for table in _tables():
            copied[table.name] = 0
            try:
                result = sdst.execution_options(stream_results=True).execute(
                    select(table))
                while True:
                    rows = result.fetchmany(batch)
                    if not rows:
                        break
                    values = [dict(row._mapping) for row in rows]
                    tdst.execute(table.insert(), values)
                    copied[table.name] += len(values)
            except SQLAlchemyError:
                pass  # 源库缺表 → 迁移 0 行
            print(f"  {table.name}: {copied[table.name]}", flush=True)
    return copied


def _reset_sequences(target) -> None:
    """Postgres SERIAL/IDENTITY 序列对齐到 max(id)。"""
    with target.begin() as conn:
        for table in _tables():
            if "id" not in table.c:
                continue
            try:
                conn.execute(text(
                    "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM " + table.name + "), 1), "
                    "(SELECT MAX(id) FROM " + table.name + ") IS NOT NULL)"
                ), {"t": table.name})
            except SQLAlchemyError:
                # 非自增主键（如 verdicts.id 是字符串）没有 sequence，跳过。
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="SQLite URL")
    ap.add_argument("--target", required=True, help="PostgreSQL URL")
    ap.add_argument("--batch", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="清空目标表；只允许演练库")
    args = ap.parse_args()
    if args.force and "prod" in args.target.lower():
        raise SystemExit("拒绝 --force 指向疑似生产库")
    src = _engine(args.source)
    with src.connect() as conn:
        _duplicate_check(conn, "users", "phone")
        _duplicate_check(conn, "users", "email")
        counts = _source_counts(conn)
    print("源库行数：")
    for name, n in counts.items():
        print(f"  {name}: {n}")

    if args.dry_run:
        print("dry-run：未连接目标库，未写入任何数据")
        return 0

    dst = _engine(args.target)
    with dst.connect() as conn:
        target_counts = _target_counts(conn)
    if any(target_counts.values()):
        if not args.force:
            raise SystemExit("目标库非空；确认是空库或显式传 --force（仅演练库）")
        with dst.begin() as conn:
            names = ", ".join(t.name for t in reversed(_tables()))
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        print("目标表已清空")

    _copy(src, dst, max(1, args.batch))
    _reset_sequences(dst)

    with dst.connect() as conn:
        after = _target_counts(conn)
    bad = {name: (counts.get(name, 0), after.get(name, 0))
           for name in counts if counts[name] != after.get(name, 0)}
    if bad:
        raise SystemExit(f"行数不一致：{bad}")
    print("迁移完成，所有表行数一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
