"""LLM capability profiles editable from admin

Revision ID: 20261106_14
Revises: 20261105_13
Create Date: 2026-11-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_14"
down_revision = "20261105_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_profiles",
        sa.Column("name", sa.String(length=16), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False,
                  server_default="openai_compatible"),
        sa.Column("base_url", sa.String(length=256), nullable=False,
                  server_default=""),
        sa.Column("model", sa.String(length=96), nullable=False,
                  server_default=""),
        sa.Column("api_key_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_price_cny_per_m", sa.Float(), nullable=False,
                  server_default="0"),
        sa.Column("output_price_cny_per_m", sa.Float(), nullable=False,
                  server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("llm_profiles")
