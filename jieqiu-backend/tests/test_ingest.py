"""ingest 管道测试：合成 collector sqlite → 导入 → 对齐 + 去重。"""
import sqlite3

from sqlalchemy import select

from app.models import SPMatch, SPSnapshot
from app.modules.ingest import import_collector_db


def _make_collector_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE matches (match_no TEXT, match_id TEXT, league TEXT,
          home TEXT, away TEXT, kickoff TEXT, single_flag INTEGER, PRIMARY KEY (match_id));
        CREATE TABLE sp_snapshots (match_id TEXT, pool TEXT, goal_line TEXT,
          sp_h REAL, sp_d REAL, sp_a REAL, captured_at TEXT,
          PRIMARY KEY (match_id, pool, captured_at));
        """
    )
    con.execute("INSERT INTO matches VALUES (?,?,?,?,?,?,?)",
                ("周三012", "2042501", "英超", "曼彻斯特城", "布莱顿", "2026-11-05 21:55:00", 1))
    con.execute("INSERT INTO matches VALUES (?,?,?,?,?,?,?)",
                ("周三013", "2042502", "英超", "Arsenal FC", "热刺", "2026-11-05 21:55:00", 1))
    for t in ("2026-11-05T10:00:00+08:00", "2026-11-05T12:00:00+08:00"):
        con.execute("INSERT INTO sp_snapshots VALUES (?,?,?,?,?,?,?)",
                    ("2042501", "had", "", 1.53, 4.40, 5.60, t))
        con.execute("INSERT INTO sp_snapshots VALUES (?,?,?,?,?,?,?)",
                    ("2042501", "hhad", "-1", 2.05, 3.60, 3.20, t))
    con.commit()
    con.close()


def test_import_align_dedup(db, tmp_path):
    p = str(tmp_path / "sp_data.db")
    _make_collector_db(p)

    r1 = import_collector_db(db, p)
    assert r1.matches_upserted == 2
    assert r1.snapshots_seen == 4
    assert r1.snapshots_inserted == 4

    # 对齐生效：曼彻斯特城 → 曼城；Arsenal FC → 阿森纳
    m1 = db.get(SPMatch, "2042501")
    assert m1.home == "曼城" and m1.home_raw == "曼彻斯特城"
    m2 = db.get(SPMatch, "2042502")
    assert m2.home == "阿森纳" and m2.home_raw == "Arsenal FC"

    # 重复导入：快照去重，场次幂等
    r2 = import_collector_db(db, p)
    assert r2.snapshots_seen == 4
    assert r2.snapshots_inserted == 0
    n = len(db.scalars(select(SPSnapshot)).all())
    assert n == 4
    assert len(db.scalars(select(SPMatch)).all()) == 2
