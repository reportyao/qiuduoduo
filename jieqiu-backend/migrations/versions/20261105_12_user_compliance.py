"""user compliance: age gate / under18 lock / self exclusion

Revision ID: 20261105_12
Revises: 20261105_11
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_12"
down_revision = "20261105_11"
branch_labels = None
depends_on = None

_COLUMNS = (
    sa.Column("age_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("birth_year", sa.Integer(), nullable=True),
    sa.Column("under18_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("self_exclusion_until", sa.DateTime(), nullable=True),
    sa.Column("self_exclusion_at", sa.DateTime(), nullable=True),
    sa.Column("self_exclusion_reason", sa.String(length=128), nullable=False,
              server_default=""),
    sa.Column("compliance_json", sa.JSON(), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in _COLUMNS:
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for name in ("compliance_json", "self_exclusion_reason",
                     "self_exclusion_at", "self_exclusion_until",
                     "under18_locked", "birth_year", "age_verified"):
            batch.drop_column(name)
