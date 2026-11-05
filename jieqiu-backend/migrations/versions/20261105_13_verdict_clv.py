"""verdict closing odds + CLV

Revision ID: 20261105_13
Revises: 20261105_12
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_13"
down_revision = "20261105_12"
branch_labels = None
depends_on = None

_COLUMNS = (
    sa.Column("closing_sp_h", sa.Float(), nullable=True),
    sa.Column("closing_sp_d", sa.Float(), nullable=True),
    sa.Column("closing_sp_a", sa.Float(), nullable=True),
    sa.Column("closing_at", sa.DateTime(), nullable=True),
    sa.Column("clv", sa.Float(), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        for column in _COLUMNS:
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("verdicts") as batch:
        for name in ("clv", "closing_at", "closing_sp_a", "closing_sp_d", "closing_sp_h"):
            batch.drop_column(name)
