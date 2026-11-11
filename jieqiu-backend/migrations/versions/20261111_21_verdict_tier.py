"""verdict tier and model status

Revision ID: 20261111_21
Revises: 20261111_20
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261111_21"
down_revision = "20261111_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("verdicts", sa.Column(
        "tier", sa.String(length=24), nullable=False, server_default="avoid"))
    op.add_column("verdicts", sa.Column(
        "model_status", sa.String(length=16), nullable=False,
        server_default="unavailable"))
    op.add_column("verdicts", sa.Column(
        "model_source", sa.String(length=16), nullable=False,
        server_default="none"))
    op.add_column("verdicts", sa.Column(
        "data_quality", sa.JSON(), nullable=True))
    op.create_index("ix_verdicts_tier", "verdicts", ["tier"])
    # 旧数据按历史状态回填；实际 tier 由 build_verdicts 重新计算。
    op.execute("""
        UPDATE verdicts SET
          tier = CASE
            WHEN status = 'promoted' THEN 'verified'
            WHEN status = 'screening' THEN 'market_reference'
            ELSE 'avoid'
          END,
          model_status = CASE WHEN model_h IS NOT NULL THEN 'shadow' ELSE 'unavailable' END,
          model_source = CASE WHEN model_h IS NOT NULL THEN 'dc' ELSE 'none' END,
          data_quality = '{}'
    """)


def downgrade() -> None:
    op.drop_index("ix_verdicts_tier", table_name="verdicts")
    op.drop_column("verdicts", "data_quality")
    op.drop_column("verdicts", "model_source")
    op.drop_column("verdicts", "model_status")
    op.drop_column("verdicts", "tier")
