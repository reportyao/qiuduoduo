"""Prediction board: product top-probability pick and full distribution

Revision ID: 20261113_26
Revises: 20261113_25
Create Date: 2026-11-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_26"
down_revision = "20261113_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sportmonks_prediction_snapshots",
                  sa.Column("product_top_pick", sa.JSON(), nullable=True))
    op.add_column("sportmonks_prediction_snapshots",
                  sa.Column("product_probs", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sportmonks_prediction_snapshots", "product_probs")
    op.drop_column("sportmonks_prediction_snapshots", "product_top_pick")
