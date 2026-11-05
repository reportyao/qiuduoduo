"""LLM gateway usage/cache/budget

Revision ID: 20261104_07
Revises: 20261104_06
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_07"
down_revision = "20261104_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column("price_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_class", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_llm_usage_request_id", "llm_usage", ["request_id"])
    op.create_index("ix_llm_usage_user_created", "llm_usage", ["user_id", "created_at"])
    op.create_index("ix_llm_usage_task_created", "llm_usage", ["task", "created_at"])
    op.create_index("ix_llm_usage_created", "llm_usage", ["created_at"])

    op.create_table(
        "llm_cache",
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("prompt_ver", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="public"),
        sa.Column("input_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_llm_cache_expires", "llm_cache", ["expires_at"])
    op.create_index("ix_llm_cache_task", "llm_cache", ["task"])

    op.create_table(
        "llm_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("limit_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reserved_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column("spent_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("day", "task", "profile",
                            name="uq_llm_budget_day_task_profile"),
    )
    op.create_index("ix_llm_budgets_day", "llm_budgets", ["day"])


def downgrade() -> None:
    op.drop_index("ix_llm_budgets_day", table_name="llm_budgets")
    op.drop_table("llm_budgets")
    op.drop_index("ix_llm_cache_task", table_name="llm_cache")
    op.drop_index("ix_llm_cache_expires", table_name="llm_cache")
    op.drop_table("llm_cache")
    op.drop_index("ix_llm_usage_created", table_name="llm_usage")
    op.drop_index("ix_llm_usage_task_created", table_name="llm_usage")
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage")
    op.drop_index("ix_llm_usage_request_id", table_name="llm_usage")
    op.drop_table("llm_usage")
