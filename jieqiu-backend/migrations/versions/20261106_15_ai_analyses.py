"""single-match AI analysis cache

Revision ID: 20261106_15
Revises: 20261106_14
Create Date: 2026-11-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_15"
down_revision = "20261106_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.String(length=16), nullable=False,
                  server_default=""),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("data_cutoff", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="ok"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=96), nullable=False,
                  server_default=""),
        sa.Column("provider", sa.String(length=32), nullable=False,
                  server_default=""),
        sa.Column("prompt_ver", sa.String(length=16), nullable=False,
                  server_default="v1"),
        sa.Column("cost_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("match_id", "input_hash",
                            name="uq_ai_analysis_match_hash"),
    )
    op.create_index("ix_ai_analyses_match_id", "ai_analyses", ["match_id"])
    op.create_index("ix_ai_analyses_match_created", "ai_analyses",
                    ["match_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_analyses_match_created", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_match_id", table_name="ai_analyses")
    op.drop_table("ai_analyses")
