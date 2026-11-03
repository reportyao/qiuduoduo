"""采集管道：采集器 SQLite（本机家宽产出）→ 应用库。

链路：读 collector db → Pandera 契约校验 → 队名对齐 → 去重入库。
任何契约违规直接抛错（fail loud），不静默入库。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contracts import validate_matches, validate_snapshots
from ..models import SPMatch, SPSnapshot
from .align import Aligner, normalize, seed_aliases


@dataclass
class IngestResult:
    matches_upserted: int
    snapshots_inserted: int
    snapshots_seen: int
    alias_unresolved: list[str]


def _read_collector(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = sqlite3.connect(path)
    try:
        matches = pd.read_sql_query(
            "select match_no, match_id, league, home, away, kickoff, single_flag from matches",
            con,
        )
        snaps = pd.read_sql_query(
            "select match_id, pool, goal_line, sp_h, sp_d, sp_a, captured_at from sp_snapshots",
            con,
        )
    finally:
        con.close()
    # collector 表列名 home/away 为原始名 → 复制为 home_raw/away_raw 语义
    matches = matches.rename(columns={})  # 保持原列，下面统一处理
    return matches, snaps


def import_collector_db(db: Session, collector_db_path: str) -> IngestResult:
    seed_aliases(db)
    aligner = Aligner(db)

    raw_m, raw_s = _read_collector(collector_db_path)

    # ---- 场次 ----
    raw_m = raw_m.rename(columns={"home": "home_raw", "away": "away_raw"})
    for col in ("match_no", "league"):
        raw_m[col] = raw_m[col].fillna("").astype(str)  # NaN → ""，防 coerce 出 "nan"
    raw_m["single_flag"] = raw_m["single_flag"].fillna(0).astype(int)
    matches_df = validate_matches(
        raw_m.assign(
            home=raw_m["home_raw"], away=raw_m["away_raw"]
        )[["match_no", "match_id", "league", "home", "away", "kickoff", "single_flag"]]
    )

    # ---- 快照 ----
    raw_s["goal_line"] = raw_s["goal_line"].fillna("")
    raw_s = raw_s.dropna(subset=["sp_h", "sp_d", "sp_a"])
    snaps_df = validate_snapshots(raw_s)

    # upsert 语句按方言选择（sqlite 开发 / postgresql=腾讯云 PG 生产，均支持 ON CONFLICT）
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as upsert_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as upsert_insert

    unresolved: list[str] = []
    m_up = 0
    for row in matches_df.itertuples(index=False):
        home = aligner.resolve(row.home)
        away = aligner.resolve(row.away)
        db.merge(
            SPMatch(
                match_id=row.match_id,
                match_no=row.match_no,
                league=row.league or "",
                home_raw=row.home,
                away_raw=row.away,
                home=home,
                away=away,
                kickoff=row.kickoff,
                single_flag=bool(row.single_flag),
            )
        )
        if home == row.home and normalize(row.home) not in aligner._map:
            unresolved.append(row.home)
        m_up += 1

    s_ins = 0
    for row in snaps_df.itertuples(index=False):
        stmt = upsert_insert(SPSnapshot.__table__).values(
            match_id=row.match_id,
            pool=row.pool,
            goal_line=row.goal_line or "",
            sp_h=float(row.sp_h),
            sp_d=float(row.sp_d),
            sp_a=float(row.sp_a),
            captured_at=row.captured_at,
        ).on_conflict_do_nothing(index_elements=["match_id", "pool", "captured_at"])
        res = db.execute(stmt)
        s_ins += res.rowcount or 0

    db.commit()
    return IngestResult(
        matches_upserted=m_up,
        snapshots_inserted=s_ins,
        snapshots_seen=len(snaps_df),
        alias_unresolved=sorted(set(unresolved))[:20],
    )
