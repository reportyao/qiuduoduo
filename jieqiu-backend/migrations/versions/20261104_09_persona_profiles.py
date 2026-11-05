"""persona profiles + copy slots

Revision ID: 20261104_09
Revises: 20261104_08
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_09"
down_revision = "20261104_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_profiles",
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("address", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("tone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("style_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("max_chars", sa.Integer(), nullable=False, server_default="220"),
        sa.Column("emoji_policy", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("allowed_emoji", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "persona_copy_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("persona_id", sa.String(length=16), nullable=False),
        sa.Column("slot_key", sa.String(length=32), nullable=False),
        sa.Column("template", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("persona_id", "slot_key", name="uq_persona_slot"),
    )
    op.create_index("ix_persona_copy_slots_persona_id", "persona_copy_slots", ["persona_id"])


def downgrade() -> None:
    op.drop_index("ix_persona_copy_slots_persona_id", table_name="persona_copy_slots")
    op.drop_table("persona_copy_slots")
    op.drop_table("persona_profiles")
