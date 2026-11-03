"""hot-path indexes + partial unique phone/email

Revision ID: 20261104_03
Revises: 20261104_02
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_03"
down_revision = "20261104_02"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_verdicts_trade_status_rake", "verdicts", ["trade_date", "rake", "status"], False),
    ("ix_verdicts_match_trade", "verdicts", ["match_id", "trade_date"], False),
    ("ix_verdicts_status_settled_kickoff", "verdicts", ["status", "settled", "kickoff"], False),
    ("ix_verdict_revisions_verdict_created", "verdict_revisions", ["verdict_id", "created_at"], False),
    ("ix_users_deleted_at", "users", ["deleted_at"], False),
    ("ix_bets_user_created", "bets", ["user_id", "created_at"], False),
    ("ix_watch_targets_type_target", "watch_targets", ["target_type", "target_id"], False),
    ("ix_events_pending", "events", ["fanout_at", "id"], False),
    ("ix_events_type_created", "events", ["type", "created_at"], False),
    ("ix_notifications_user_channel_opened", "notifications", ["user_id", "channel", "opened_at"], False),
    ("ix_notifications_status_scheduled", "notifications", ["status", "scheduled_at"], False),
    ("ix_notifications_created_at", "notifications", ["created_at"], False),
    ("ix_user_events_user_created", "user_events", ["user_id", "created_at"], False),
    ("ix_model_runs_match_date_gate", "model_runs", ["match_id", "run_date", "gate"], False),
    ("ix_model_runs_created_at", "model_runs", ["created_at"], False),
    ("ix_verification_codes_target_purpose_expires", "verification_codes", ["target_hash", "purpose", "expires_at"], False),
    ("ix_verification_codes_created_at", "verification_codes", ["created_at"], False),
    ("ix_refresh_tokens_user_revoked", "refresh_tokens", ["user_id", "revoked"], False),
    ("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], False),
]


def upgrade() -> None:
    for name, table, cols, unique in INDEXES:
        op.create_index(name, table, cols, unique=unique)

    # 部分唯一索引：NULL 不参与唯一性。旧库可能已由 init_db 创建，用 IF NOT EXISTS。
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone "
            "ON users (phone) WHERE phone IS NOT NULL"))
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email "
            "ON users (email) WHERE email IS NOT NULL"))
    else:
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users (phone)"))
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)"))


def downgrade() -> None:
    for name, _table, _cols, _unique in reversed(INDEXES):
        op.drop_index(name)
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_phone"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_email"))
