"""index verdicts.settled_at for settlement monitor

Revision ID: 20261104_04
Revises: 20261104_03
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "20261104_04"
down_revision = "20261104_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_verdicts_settled_at", "verdicts", ["settled_at"])


def downgrade() -> None:
    op.drop_index("ix_verdicts_settled_at", table_name="verdicts")
