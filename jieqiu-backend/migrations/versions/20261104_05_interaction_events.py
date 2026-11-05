"""add interaction_events for focus/action funnel

Revision ID: 20261104_05
Revises: 20261104_04
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_05"
down_revision = "20261104_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("schema_ver", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("user_id", sa.String(length=40), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("verdict_id", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_interaction_events_event_id", "interaction_events", ["event_id"], unique=True)
    op.create_index("ix_interaction_events_user_id", "interaction_events", ["user_id"])
    op.create_index("ix_interaction_events_event_created", "interaction_events", ["event", "created_at"])
    op.create_index("ix_interaction_events_match_created", "interaction_events", ["match_id", "created_at"])
    op.create_index("ix_interaction_events_user_created", "interaction_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_interaction_events_user_created", table_name="interaction_events")
    op.drop_index("ix_interaction_events_match_created", table_name="interaction_events")
    op.drop_index("ix_interaction_events_event_created", table_name="interaction_events")
    op.drop_index("ix_interaction_events_user_id", table_name="interaction_events")
    op.drop_index("ix_interaction_events_event_id", table_name="interaction_events")
    op.drop_table("interaction_events")
