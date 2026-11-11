"""ai research facts hash for llm cache

Revision ID: 20261111_20
Revises: 20261111_19
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_20"
down_revision = "20261111_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_research", sa.Column(
        "facts_hash", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("ai_research", "facts_hash")
