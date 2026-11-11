"""llm profile reasoning switch

Revision ID: 20261111_19
Revises: 20261111_18
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_19"
down_revision = "20261111_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_profiles", sa.Column(
        "reasoning", sa.String(length=8), nullable=False, server_default="auto"))


def downgrade() -> None:
    op.drop_column("llm_profiles", "reasoning")
