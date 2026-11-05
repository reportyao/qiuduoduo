"""decision snapshots + review runs + publish lifecycle

Revision ID: 20261105_10
Revises: 20261104_09
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_10"
down_revision = "20261104_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_snapshots",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("match_no", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("verdict_id", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("trade_date", "match_id", "version",
                            name="uq_decision_snapshot_version"),
    )
    op.create_index("ix_decision_snapshots_trade_date", "decision_snapshots", ["trade_date"])
    op.create_index("ix_decision_snapshots_match_id", "decision_snapshots", ["match_id"])
    op.create_index("ix_decision_snapshots_verdict_id", "decision_snapshots", ["verdict_id"])
    op.create_index("ix_decision_snapshots_status", "decision_snapshots", ["status"])
    op.create_index("ix_decision_snapshots_payload_hash", "decision_snapshots", ["payload_hash"])
    op.create_index("ix_decision_snapshots_source_hash", "decision_snapshots", ["source_hash"])
    op.create_index("ix_decision_snapshots_trade_status", "decision_snapshots",
                    ["trade_date", "status"])
    op.create_index("ix_decision_snapshots_match_trade", "decision_snapshots",
                    ["match_id", "trade_date"])

    op.create_table(
        "recommendation_plans",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("risk_profile", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("label", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("legs", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("trade_date", "risk_profile", "version",
                            name="uq_recommendation_plan_version"),
    )
    op.create_index("ix_recommendation_plans_trade_date", "recommendation_plans", ["trade_date"])
    op.create_index("ix_recommendation_plans_risk_profile", "recommendation_plans", ["risk_profile"])
    op.create_index("ix_recommendation_plans_status", "recommendation_plans", ["status"])
    op.create_index("ix_recommendation_plans_payload_hash", "recommendation_plans", ["payload_hash"])
    op.create_index("ix_recommendation_plans_source_hash", "recommendation_plans", ["source_hash"])
    op.create_index("ix_recommendation_plans_trade_status", "recommendation_plans",
                    ["trade_date", "status"])

    op.create_table(
        "review_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="failed"),
        sa.Column("layers", sa.JSON(), nullable=False),
        sa.Column("reviewer", sa.String(length=64), nullable=False, server_default="rules"),
        sa.Column("prompt_ver", sa.String(length=32), nullable=False, server_default="review-v1"),
        sa.Column("llm_degraded", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_review_runs_subject_type", "review_runs", ["subject_type"])
    op.create_index("ix_review_runs_subject_id", "review_runs", ["subject_id"])
    op.create_index("ix_review_runs_status", "review_runs", ["status"])
    op.create_index("ix_review_runs_subject", "review_runs", ["subject_type", "subject_id"])
    op.create_index("ix_review_runs_created", "review_runs", ["created_at"])

    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("to_status", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="pipeline"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recommendation_events_subject_type", "recommendation_events",
                    ["subject_type"])
    op.create_index("ix_recommendation_events_subject_id", "recommendation_events",
                    ["subject_id"])
    op.create_index("ix_recommendation_events_subject", "recommendation_events",
                    ["subject_type", "subject_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_events_subject", table_name="recommendation_events")
    op.drop_index("ix_recommendation_events_subject_id", table_name="recommendation_events")
    op.drop_index("ix_recommendation_events_subject_type", table_name="recommendation_events")
    op.drop_table("recommendation_events")

    op.drop_index("ix_review_runs_created", table_name="review_runs")
    op.drop_index("ix_review_runs_subject", table_name="review_runs")
    op.drop_index("ix_review_runs_status", table_name="review_runs")
    op.drop_index("ix_review_runs_subject_id", table_name="review_runs")
    op.drop_index("ix_review_runs_subject_type", table_name="review_runs")
    op.drop_table("review_runs")

    op.drop_index("ix_recommendation_plans_trade_status", table_name="recommendation_plans")
    op.drop_index("ix_recommendation_plans_source_hash", table_name="recommendation_plans")
    op.drop_index("ix_recommendation_plans_payload_hash", table_name="recommendation_plans")
    op.drop_index("ix_recommendation_plans_status", table_name="recommendation_plans")
    op.drop_index("ix_recommendation_plans_risk_profile", table_name="recommendation_plans")
    op.drop_index("ix_recommendation_plans_trade_date", table_name="recommendation_plans")
    op.drop_table("recommendation_plans")

    op.drop_index("ix_decision_snapshots_match_trade", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_trade_status", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_source_hash", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_payload_hash", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_status", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_verdict_id", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_match_id", table_name="decision_snapshots")
    op.drop_index("ix_decision_snapshots_trade_date", table_name="decision_snapshots")
    op.drop_table("decision_snapshots")
