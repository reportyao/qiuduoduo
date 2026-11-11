"""sportmonks match data

Revision ID: 20261111_17
Revises: 20261106_16
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_17"
down_revision = "20261106_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sportmonks_match_data",
        sa.Column("match_id", sa.String(length=32), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("home_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("away_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("kickoff_utc", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("probs", sa.JSON(), nullable=True),
        sa.Column("odds", sa.JSON(), nullable=True),
        sa.Column("bookmaker", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="sportmonks"),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("data_cutoff", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sportmonks_match_data_fixture_id", "sportmonks_match_data",
                    ["fixture_id"])


def downgrade() -> None:
    op.drop_index("ix_sportmonks_match_data_fixture_id", table_name="sportmonks_match_data")
    op.drop_table("sportmonks_match_data")
