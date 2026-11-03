"""add bets.sp odds snapshot for correct P&L

Revision ID: 20261104_02
Revises: 71af760b1e99
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_02"
down_revision = "71af760b1e99"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bets", sa.Column("sp", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("bets", "sp")
