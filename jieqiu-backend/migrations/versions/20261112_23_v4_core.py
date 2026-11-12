"""v4.1 settlement / plans / membership / performance / OPC / memory

Revision ID: 20261112_23
Revises: 20261111_22
Create Date: 2026-11-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261112_23"
down_revision = "20261111_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 90 分钟口径字段
    op.add_column("match_results", sa.Column("fixture_id", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("status", sa.String(8), nullable=False, server_default="FT"))
    op.add_column("match_results", sa.Column("ft_home", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("ft_away", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("ht_home", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("ht_away", sa.Integer(), nullable=True))
    op.add_column("match_results", sa.Column("events_json", sa.JSON(), nullable=True))
    op.add_column("match_results", sa.Column("raw_hash", sa.String(64), nullable=False, server_default=""))
    op.create_index("ix_match_results_fixture_id", "match_results", ["fixture_id"])

    op.create_table(
        "market_settlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("leg_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("market", sa.String(16), nullable=False, server_default="had"),
        sa.Column("line", sa.String(16), nullable=False, server_default=""),
        sa.Column("direction", sa.String(16), nullable=False, server_default=""),
        sa.Column("rules_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("result", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("won", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(24), nullable=False, server_default=""),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("subject_type", "subject_id", "leg_index", "market",
                            "line", "direction", "rules_version",
                            name="uq_market_settlement"),
    )
    op.create_index("ix_market_settlements_subject", "market_settlements",
                    ["subject_type", "subject_id"])
    op.create_index("ix_market_settlements_settled", "market_settlements", ["settled_at"])

    op.create_table(
        "performance_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("trade_date", sa.String(10), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default=""),
        sa.Column("market", sa.String(16), nullable=False, server_default=""),
        sa.Column("picks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hit_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("roi", sa.Float(), nullable=True),
        sa.Column("clv", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("scope", "trade_date", "risk_level", "market",
                            name="uq_performance_daily"),
    )
    op.create_index("ix_performance_daily_scope_date", "performance_daily",
                    ["scope", "trade_date"])

    op.create_table(
        "plan_cycles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(32), nullable=False, server_default="稳健定投"),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_at", sa.String(32), nullable=False, server_default=""),
        sa.Column("end_at", sa.String(32), nullable=False, server_default=""),
        sa.Column("budget", sa.Float(), nullable=False, server_default="400"),
        sa.Column("target_matches", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("total_stake", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_return", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("roi", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("selection_version", sa.String(24), nullable=False, server_default="v1"),
        sa.Column("model_version", sa.String(24), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("risk_level", "cycle_no", name="uq_plan_cycle_no"),
    )
    op.create_index("ix_plan_cycles_status_start", "plan_cycles", ["status", "start_at"])

    op.create_table(
        "plan_bets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("cycle_id", sa.String(32), nullable=False, index=True),
        sa.Column("bet_type", sa.String(12), nullable=False, server_default="single"),
        sa.Column("label", sa.String(64), nullable=False, server_default=""),
        sa.Column("stake", sa.Float(), nullable=False, server_default="100"),
        sa.Column("odds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plan_bets_cycle", "plan_bets", ["cycle_id"])

    op.create_table(
        "plan_bet_legs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bet_id", sa.String(32), nullable=False, index=True),
        sa.Column("verdict_id", sa.String(40), nullable=False, index=True),
        sa.Column("match_id", sa.String(32), nullable=False, server_default=""),
        sa.Column("market", sa.String(16), nullable=False, server_default="had"),
        sa.Column("line", sa.String(16), nullable=False, server_default=""),
        sa.Column("direction", sa.String(16), nullable=False, server_default=""),
        sa.Column("odds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("allocation", sa.Float(), nullable=False, server_default="100"),
        sa.Column("model_prob", sa.Float(), nullable=True),
        sa.Column("market_prob", sa.Float(), nullable=True),
        sa.Column("edge", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("selection_reason", sa.String(240), nullable=False, server_default=""),
        sa.Column("result", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plan_bet_legs_bet", "plan_bet_legs", ["bet_id"])
    op.create_index("ix_plan_bet_legs_verdict", "plan_bet_legs", ["verdict_id"])

    op.create_table(
        "user_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("tier", sa.String(8), nullable=False, server_default="pro"),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="admin_manual"),
        sa.Column("granted_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_memberships_user_status", "user_memberships", ["user_id", "status"])
    op.create_index("uq_user_memberships_active", "user_memberships", ["user_id"],
                    unique=True, sqlite_where=sa.text("status = 'active'"),
                    postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "membership_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("action", sa.String(16), nullable=False, server_default="grant"),
        sa.Column("tier", sa.String(8), nullable=False, server_default=""),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("actor", sa.String(64), nullable=False, server_default=""),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_membership_events_user", "membership_events", ["user_id", "created_at"])

    op.create_table(
        "analysis_quota",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("trade_date", sa.String(10), nullable=False, index=True),
        sa.Column("limit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "trade_date", name="uq_analysis_quota"),
    )
    op.create_table(
        "analysis_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("trade_date", sa.String(10), nullable=False, index=True),
        sa.Column("match_id", sa.String(32), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "trade_date", "match_id", name="uq_analysis_usage"),
    )

    op.create_table(
        "market_access",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tier", sa.String(8), nullable=False, index=True),
        sa.Column("market_key", sa.String(24), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.String(120), nullable=False, server_default=""),
        sa.UniqueConstraint("tier", "market_key", name="uq_market_access"),
    )

    op.create_table(
        "engine_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(16), nullable=False, server_default="V3.21"),
        sa.Column("markets_monitored", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("models_reviewing", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("data_points_factor", sa.Float(), nullable=False, server_default="5"),
        sa.Column("updated_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute("INSERT INTO engine_config (id, version, markets_monitored, models_reviewing, data_points_factor, updated_by) "
               "VALUES (1, 'V3.21', 5, 7, 5, 'migration')")

    op.create_table(
        "ops_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_key", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(300), nullable=False, server_default=""),
    )
    op.create_index("ix_ops_jobs_key_started", "ops_jobs", ["job_key", "started_at"])

    op.create_table(
        "ops_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(32), nullable=False, index=True),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(32), nullable=False, server_default=""),
        sa.Column("message", sa.String(400), nullable=False, server_default=""),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ops_exceptions_status_created", "ops_exceptions", ["status", "created_at"])

    op.create_table(
        "user_profile_features",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("feature", sa.String(32), nullable=False, index=True),
        sa.Column("value", sa.String(256), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(16), nullable=False, server_default="behavior"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "feature", name="uq_user_profile_feature"),
    )

    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("match_id", sa.String(32), nullable=False, server_default=""),
        sa.Column("summary", sa.String(1000), nullable=False, server_default=""),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_assistant_threads_user", "assistant_threads", ["user_id", "updated_at"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.String(32), nullable=False, index=True),
        sa.Column("user_id", sa.String(40), nullable=False, index=True),
        sa.Column("role", sa.String(12), nullable=False, server_default="assistant"),
        sa.Column("persona", sa.String(16), nullable=False, server_default="zhuanjia"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("facts_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("copy_version", sa.String(32), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_assistant_messages_thread", "assistant_messages", ["thread_id", "created_at"])

    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(32), nullable=False, index=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("features_json", sa.JSON(), nullable=True),
        sa.Column("market_json", sa.JSON(), nullable=True),
        sa.Column("lineup_json", sa.JSON(), nullable=True),
        sa.Column("feature_hash", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_feature_snapshots_match_time", "feature_snapshots", ["match_id", "captured_at"])

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, index=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("league", sa.String(64), nullable=False, server_default=""),
        sa.Column("market", sa.String(16), nullable=False, server_default="had"),
        sa.Column("status", sa.String(16), nullable=False, server_default="shadow"),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", "version", name="uq_model_registry"),
    )

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("league", sa.String(64), nullable=False, server_default=""),
        sa.Column("market", sa.String(16), nullable=False, server_default="had"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(300), nullable=False, server_default=""),
    )
    op.create_index("ix_training_runs_started", "training_runs", ["started_at"])


def downgrade() -> None:
    for table in ("training_runs", "model_registry", "feature_snapshots",
                  "assistant_messages", "assistant_threads", "user_profile_features",
                  "ops_exceptions", "ops_jobs", "engine_config", "market_access",
                  "analysis_usage", "analysis_quota", "membership_events",
                  "user_memberships", "plan_bet_legs", "plan_bets", "plan_cycles",
                  "performance_daily", "market_settlements"):
        op.drop_table(table)
    op.drop_index("ix_match_results_fixture_id", table_name="match_results")
    for col in ("raw_hash", "events_json", "ht_away", "ht_home",
                "ft_away", "ft_home", "status", "fixture_id"):
        op.drop_column("match_results", col)
