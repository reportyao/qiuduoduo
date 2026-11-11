"""ai research

Revision ID: 20261111_18
Revises: 20261111_17
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_18"
down_revision = "20261111_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_research",
        sa.Column("match_id", sa.String(length=32), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="unavailable"),
        sa.Column("headline", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("points", sa.JSON(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(length=300), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("ai_research")
