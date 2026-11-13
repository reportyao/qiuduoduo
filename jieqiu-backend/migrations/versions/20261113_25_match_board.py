"""Match board: live state, frozen prediction snapshots and settlements

Revision ID: 20261113_25
Revises: 20261112_24
Create Date: 2026-11-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_25"
down_revision = "20261112_24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sp_pool_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(32), nullable=False),
        sa.Column("pool", sa.String(12), nullable=False),
        sa.Column("line", sa.String(16), nullable=False, server_default=""),
        sa.Column("selections", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("match_id", "pool", "captured_at",
                            name="uq_sp_pool_snapshot"),
    )
    op.create_index("ix_sp_pool_snapshots_match_pool", "sp_pool_snapshots",
                    ["match_id", "pool"])

    op.create_table(
        "sportmonks_live_state",
        sa.Column("match_id", sa.String(32), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("state_short", sa.String(16), nullable=False, server_default=""),
        sa.Column("minute", sa.String(8), nullable=False, server_default=""),
        sa.Column("score_home", sa.Integer(), nullable=True),
        sa.Column("score_away", sa.Integer(), nullable=True),
        sa.Column("ht_home", sa.Integer(), nullable=True),
        sa.Column("ht_away", sa.Integer(), nullable=True),
        sa.Column("periods", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sportmonks_live_state_fixture",
                    "sportmonks_live_state", ["fixture_id"])
    op.create_index("ix_sportmonks_live_state_state",
                    "sportmonks_live_state", ["state_short"])

    op.create_table(
        "sportmonks_prediction_snapshots",
        sa.Column("match_id", sa.String(32), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("kickoff_cn", sa.String(32), nullable=False, server_default=""),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("cutoff_reason", sa.String(24), nullable=False,
                  server_default="pre_kickoff"),
        sa.Column("predictions", sa.JSON(), nullable=True),
        sa.Column("market_lines", sa.JSON(), nullable=True),
        sa.Column("product_pick", sa.JSON(), nullable=True),
        sa.Column("verdict_id", sa.String(40), nullable=True),
        sa.Column("snapshot_source", sa.String(24), nullable=False,
                  server_default="sportmonks"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
    )
    op.create_index("ix_sm_prediction_snapshots_kickoff",
                    "sportmonks_prediction_snapshots", ["kickoff_cn"])
    op.create_index("ix_sm_prediction_snapshots_locked",
                    "sportmonks_prediction_snapshots", ["locked_at"])
    op.create_index("ix_sm_prediction_snapshots_fixture",
                    "sportmonks_prediction_snapshots", ["fixture_id"])

    op.create_table(
        "sportmonks_prediction_settlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(32), nullable=False),
        sa.Column("fixture_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kickoff_cn", sa.String(32), nullable=False, server_default=""),
        sa.Column("source", sa.String(16), nullable=False, server_default="sportmonks"),
        sa.Column("prediction_type", sa.String(64), nullable=False),
        sa.Column("prediction_label", sa.String(128), nullable=False, server_default=""),
        sa.Column("predicted_key", sa.String(64), nullable=False, server_default=""),
        sa.Column("predicted_label", sa.String(128), nullable=False, server_default=""),
        sa.Column("predicted_probability", sa.Float(), nullable=True),
        sa.Column("market_line", sa.String(16), nullable=False, server_default=""),
        sa.Column("actual_key", sa.String(64), nullable=False, server_default=""),
        sa.Column("actual_label", sa.String(128), nullable=False, server_default=""),
        sa.Column("result", sa.String(24), nullable=False,
                  server_default="insufficient_data"),
        sa.Column("counted_in_accuracy", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("rule_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("settled_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("match_id", "source", "prediction_type",
                            name="uq_sm_settlement_match_source_type"),
    )
    op.create_index("ix_sm_settlement_counted_result",
                    "sportmonks_prediction_settlements",
                    ["counted_in_accuracy", "result"])
    op.create_index("ix_sm_settlement_kickoff",
                    "sportmonks_prediction_settlements", ["kickoff_cn"])
    op.create_index("ix_sm_settlement_match",
                    "sportmonks_prediction_settlements", ["match_id"])

    op.create_table(
        "match_result_details",
        sa.Column("result_id", sa.Integer(), primary_key=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actuals", sa.JSON(), nullable=True),
        sa.Column("stats_captured_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_match_result_details_fixture",
                    "match_result_details", ["fixture_id"])


def downgrade() -> None:
    op.drop_index("ix_match_result_details_fixture", table_name="match_result_details")
    op.drop_table("match_result_details")
    op.drop_index("ix_sm_settlement_match", table_name="sportmonks_prediction_settlements")
    op.drop_index("ix_sm_settlement_kickoff", table_name="sportmonks_prediction_settlements")
    op.drop_index("ix_sm_settlement_counted_result",
                  table_name="sportmonks_prediction_settlements")
    op.drop_table("sportmonks_prediction_settlements")
    op.drop_index("ix_sm_prediction_snapshots_fixture",
                  table_name="sportmonks_prediction_snapshots")
    op.drop_index("ix_sm_prediction_snapshots_locked",
                  table_name="sportmonks_prediction_snapshots")
    op.drop_index("ix_sm_prediction_snapshots_kickoff",
                  table_name="sportmonks_prediction_snapshots")
    op.drop_table("sportmonks_prediction_snapshots")
    op.drop_index("ix_sportmonks_live_state_state", table_name="sportmonks_live_state")
    op.drop_index("ix_sportmonks_live_state_fixture", table_name="sportmonks_live_state")
    op.drop_table("sportmonks_live_state")
    op.drop_index("ix_sp_pool_snapshots_match_pool", table_name="sp_pool_snapshots")
    op.drop_table("sp_pool_snapshots")
