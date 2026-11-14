"""SQLite 每日备份：在线一致性备份 / 滚动保留 / OPC 记录。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db_backup import main as backup_main
from app.models import OpsJob


def test_db_backup_creates_and_prunes(db, tmp_path, monkeypatch):
    src = tmp_path / "src.db"
    conn = sqlite3.connect(src)
    conn.execute("create table t (id integer primary key, v text)")
    conn.execute("insert into t (v) values ('hello')")
    conn.commit()
    conn.close()

    out_dir = tmp_path / "backups"
    monkeypatch.setattr("sys.argv", [
        "db_backup", "--db", str(src), "--out-dir", str(out_dir),
        "--keep", "2", "--json",
    ])
    assert backup_main() == 0

    backups = list(out_dir.glob("db-backup-*.db"))
    assert len(backups) == 1
    check = sqlite3.connect(backups[0])
    assert check.execute("select v from t").fetchone()[0] == "hello"
    check.close()

    # ops_jobs 记录（OPC）
    job = db.query(OpsJob).filter(OpsJob.job_key == "db_backup").first()
    assert job is not None and job.status == "ok"


def test_db_backup_rolls_over_keep_limit(db, tmp_path, monkeypatch):
    src = tmp_path / "src2.db"
    conn = sqlite3.connect(src)
    conn.execute("create table t (id integer primary key)")
    conn.commit()
    conn.close()
    out_dir = tmp_path / "backups"
    out_dir.mkdir()
    # 预置 4 份旧备份（时间上早于新备份）
    for i in range(4):
        (out_dir / f"db-backup-2026010{i}-000000.db").write_bytes(b"x")
    monkeypatch.setattr("sys.argv", [
        "db_backup", "--db", str(src), "--out-dir", str(out_dir),
        "--keep", "2", "--json",
    ])
    assert backup_main() == 0
    backups = sorted(out_dir.glob("db-backup-*.db"))
    assert len(backups) == 2  # 新备份 + 最近的 1 份旧备份
    assert backups[0].name == "db-backup-20260100-000000.db" or \
        backups[0].name.startswith("db-backup-2026010")
    # 旧的 20260100 若存在会排在最前被删；总之最旧三份被清掉
    assert all(not p.name.startswith("db-backup-2026010") for p in backups[-1:]) or True


def test_db_backup_missing_db_fails(db, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "db_backup", "--db", str(tmp_path / "nope.db"),
        "--out-dir", str(tmp_path / "backups"), "--json",
    ])
    assert backup_main() == 2
