"""persona llm model pool + copy cache

Revision ID: 20261104_08
Revises: 20261104_07
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_08"
down_revision = "20261104_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_llm_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("base_url", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("api_key_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeout_s", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.4"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=256), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("base_url", "model", name="uq_persona_llm_base_model"),
    )
    op.create_index("ix_persona_llm_models_priority", "persona_llm_models", ["priority"])

    op.create_table(
        "persona_copy_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("source_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("persona", sa.String(length=16), nullable=False, server_default="zhuanjia"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_key", "source_hash", "persona",
                            name="uq_persona_copy_source_hash_persona"),
    )
    op.create_index("ix_persona_copy_created", "persona_copy_cache", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_persona_copy_created", table_name="persona_copy_cache")
    op.drop_table("persona_copy_cache")
    op.drop_index("ix_persona_llm_models_priority", table_name="persona_llm_models")
    op.drop_table("persona_llm_models")
