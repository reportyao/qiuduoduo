"""Sportmonks fixture intelligence / predictions / selected markets

Revision ID: 20261112_24
Revises: 20261112_23
Create Date: 2026-11-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261112_24"
down_revision = "20261112_23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sportmonks_fixture_intel",
        sa.Column("match_id", sa.String(32), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(128), nullable=False, server_default=""),
        sa.Column("home_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("away_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("kickoff_utc", sa.String(32), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("data_cutoff", sa.String(32), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sportmonks_fixture_intel_fixture", "sportmonks_fixture_intel",
                    ["fixture_id"])

    op.create_table(
        "sportmonks_predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(32), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("type_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("type_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("probabilities", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("match_id", "type_id", name="uq_sm_prediction_match_type"),
    )
    op.create_index("ix_sm_predictions_match", "sportmonks_predictions", ["match_id"])

    op.create_table(
        "sportmonks_markets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(32), nullable=False),
        sa.Column("market_key", sa.String(32), nullable=False),
        sa.Column("market_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("bookmaker", sa.String(32), nullable=False, server_default=""),
        sa.Column("line", sa.String(16), nullable=False, server_default=""),
        sa.Column("selections", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("match_id", "market_key", name="uq_sm_market_match_key"),
    )
    op.create_index("ix_sm_markets_match", "sportmonks_markets", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_sm_markets_match", table_name="sportmonks_markets")
    op.drop_table("sportmonks_markets")
    op.drop_index("ix_sm_predictions_match", table_name="sportmonks_predictions")
    op.drop_table("sportmonks_predictions")
    op.drop_index("ix_sportmonks_fixture_intel_fixture", table_name="sportmonks_fixture_intel")
    op.drop_table("sportmonks_fixture_intel")
