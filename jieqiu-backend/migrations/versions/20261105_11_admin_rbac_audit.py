"""admin users + audit log

Revision ID: 20261105_11
Revises: 20261105_10
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_11"
down_revision = "20261105_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="operator"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("username", name="uq_admin_users_username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)

    op.create_table(
        "admin_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("target_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_audit_created", "admin_audit", ["created_at"])
    op.create_index("ix_admin_audit_actor", "admin_audit", ["actor"])
    op.create_index("ix_admin_audit_action", "admin_audit", ["action"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_action", table_name="admin_audit")
    op.drop_index("ix_admin_audit_actor", table_name="admin_audit")
    op.drop_index("ix_admin_audit_created", table_name="admin_audit")
    op.drop_table("admin_audit")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
