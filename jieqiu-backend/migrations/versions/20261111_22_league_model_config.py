"""league model config for per-league gating

Revision ID: 20261111_22
Revises: 20261111_21
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_22"
down_revision = "20261111_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_model_config",
        sa.Column("league", sa.String(length=64), primary_key=True),
        sa.Column("dc_status", sa.String(length=12), nullable=False,
                  server_default="shadow"),
        sa.Column("sm_status", sa.String(length=12), nullable=False,
                  server_default="disabled"),
        sa.Column("dc_weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("sm_weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brier_dc", sa.Float(), nullable=True),
        sa.Column("brier_market", sa.Float(), nullable=True),
        sa.Column("rps_dc", sa.Float(), nullable=True),
        sa.Column("rps_market", sa.Float(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("league_model_config")
