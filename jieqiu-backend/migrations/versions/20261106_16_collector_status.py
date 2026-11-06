"""collector heartbeat and restart command

Revision ID: 20261106_16
Revises: 20261106_15
Create Date: 2026-11-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_16"
down_revision = "20261106_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("pid", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("cycle", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshots_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_push_at", sa.DateTime(), nullable=True),
        sa.Column("restart_requested_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("collector_status")
