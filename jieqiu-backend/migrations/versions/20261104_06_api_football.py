"""API-Football fixtures/lineups/injuries/standings/usage

Revision ID: 20261104_06
Revises: 20261104_05
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261104_06"
down_revision = "20261104_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_football_fixtures",
        sa.Column("fixture_id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.String(length=32), nullable=True),
        sa.Column("league_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("league_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("home_team_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("home_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("away_team_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("away_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("kickoff_utc", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("status_short", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("status_long", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("venue", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("link_method", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("link_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lineups_synced_at", sa.DateTime(), nullable=True),
        sa.Column("injuries_synced_at", sa.DateTime(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_af_fixtures_kickoff", "api_football_fixtures", ["kickoff_utc"])
    op.create_index("ix_af_fixtures_league_season", "api_football_fixtures", ["league_id", "season"])
    op.create_index("ix_af_fixtures_match", "api_football_fixtures", ["match_id"])

    op.create_table(
        "match_lineups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("side", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("formation", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("coach", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("starters", sa.JSON(), nullable=False),
        sa.Column("subs", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fixture_id", "team_id", name="uq_lineup_fixture_team"),
    )
    op.create_index("ix_match_lineups_fixture_id", "match_lineups", ["fixture_id"])
    op.create_index("ix_lineups_match", "match_lineups", ["match_id"])

    op.create_table(
        "match_injuries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("side", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("player_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("player_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fixture_id", "player_id", "type", name="uq_injury_fixture_player_type"),
    )
    op.create_index("ix_match_injuries_fixture_id", "match_injuries", ["fixture_id"])
    op.create_index("ix_injuries_match", "match_injuries", ["match_id"])

    op.create_table(
        "team_standings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("league_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("team_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals_for", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("goals_against", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("form", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("league_id", "season", "team_id", name="uq_standing_league_season_team"),
    )
    op.create_index("ix_standings_league_season", "team_standings", ["league_id", "season"])

    op.create_table(
        "api_football_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("day", "endpoint", name="uq_af_usage_day_endpoint"),
    )
    op.create_index("ix_api_football_usage_day", "api_football_usage", ["day"])


def downgrade() -> None:
    op.drop_index("ix_api_football_usage_day", table_name="api_football_usage")
    op.drop_table("api_football_usage")
    op.drop_index("ix_standings_league_season", table_name="team_standings")
    op.drop_table("team_standings")
    op.drop_index("ix_injuries_match", table_name="match_injuries")
    op.drop_index("ix_match_injuries_fixture_id", table_name="match_injuries")
    op.drop_table("match_injuries")
    op.drop_index("ix_lineups_match", table_name="match_lineups")
    op.drop_index("ix_match_lineups_fixture_id", table_name="match_lineups")
    op.drop_table("match_lineups")
    op.drop_index("ix_af_fixtures_match", table_name="api_football_fixtures")
    op.drop_index("ix_af_fixtures_league_season", table_name="api_football_fixtures")
    op.drop_index("ix_af_fixtures_kickoff", table_name="api_football_fixtures")
    op.drop_table("api_football_fixtures")
