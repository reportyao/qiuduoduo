"""数据契约（Pandera）：所有进入管道的 DataFrame 先过契约再入库（TechSpec §2 纪律）。

契约失败 = 管道停止，坏数据不允许静默入库。
"""
from __future__ import annotations

import pandera.pandas as pa
from pandera import Check, Column, DataFrameSchema

POOL_VALUES = ["had", "hhad"]

sp_match_schema = DataFrameSchema(
    {
        "match_no": Column(str, Check.str_length(0, 16)),
        "match_id": Column(str, Check.str_length(1, 32)),
        "league": Column(str, Check.str_length(0, 64)),
        "home": Column(str, Check.str_length(1, 128)),
        "away": Column(str, Check.str_length(1, 128)),
        "kickoff": Column(
            str,
            Check.str_matches(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
        ),
        "single_flag": Column(int, Check.isin([0, 1])),
    },
    strict=False,
    coerce=True,
)

sp_snapshot_schema = DataFrameSchema(
    {
        "match_id": Column(str, Check.str_length(1, 32)),
        "pool": Column(str, Check.isin(POOL_VALUES)),
        "goal_line": Column(str, Check.str_length(0, 8), nullable=True),
        "sp_h": Column(float, Check.in_range(1.0, 1000.0)),
        "sp_d": Column(float, Check.in_range(1.0, 1000.0)),
        "sp_a": Column(float, Check.in_range(1.0, 1000.0)),
        "captured_at": Column(
            str,
            Check.str_matches(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$"),
        ),
    },
    strict=False,
    coerce=True,
)


def validate_matches(df):
    return sp_match_schema.validate(df, lazy=True)


def validate_snapshots(df):
    return sp_snapshot_schema.validate(df, lazy=True)
