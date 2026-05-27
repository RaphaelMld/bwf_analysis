"""initial schema

Revision ID: f27f3dbcd684
Revises: 
Create Date: 2025-05-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f27f3dbcd684"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bwf_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("bwf_code", sa.String(36), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("country", sa.String(100)),
        sa.Column("prize_money", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bwf_id", sa.String(20), nullable=False, unique=True),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(3)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bwf_match_id", sa.BigInteger(), nullable=False),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id"), nullable=False),
        sa.Column("discipline", sa.String(2), nullable=False),
        sa.Column("round_name", sa.String(50)),
        sa.Column("match_time_utc", sa.DateTime()),
        sa.Column("player1_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("player2_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("player1_seed", sa.SmallInteger()),
        sa.Column("player2_seed", sa.SmallInteger()),
        sa.Column("winner", sa.SmallInteger()),
        sa.Column("score_status", sa.SmallInteger(), server_default="0"),
        sa.Column("duration_minutes", sa.SmallInteger()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("bwf_match_id", name="uq_matches_bwf_id"),
    )
    op.create_table(
        "set_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("set_number", sa.SmallInteger(), nullable=False),
        sa.Column("score_player1", sa.SmallInteger(), nullable=False),
        sa.Column("score_player2", sa.SmallInteger(), nullable=False),
    )
    op.create_table(
        "ratings_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("discipline", sa.String(2), nullable=False),
        sa.Column("rating_type", sa.String(20), nullable=False),
        sa.Column("rating_value", sa.Float(), nullable=False),
        sa.Column("matches_played", sa.Integer(), server_default="0"),
        sa.Column("after_match_id", sa.Integer(), sa.ForeignKey("matches.id")),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "bwf_rankings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("discipline", sa.String(2), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("week_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("player_id", "discipline", "week_date", name="uq_ranking_player_week"),
    )
    op.create_table(
        "scraping_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("retry_count", sa.SmallInteger(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # Index utiles pour les requêtes analytiques
    op.create_index("ix_matches_tournament_discipline", "matches", ["tournament_id", "discipline"])
    op.create_index("ix_matches_player1", "matches", ["player1_id"])
    op.create_index("ix_matches_player2", "matches", ["player2_id"])
    op.create_index("ix_ratings_player_discipline", "ratings_history", ["player_id", "discipline"])
    op.create_index("ix_rankings_week_discipline", "bwf_rankings", ["week_date", "discipline"])
    op.create_index("ix_scraping_jobs_status", "scraping_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("scraping_jobs")
    op.drop_table("bwf_rankings")
    op.drop_table("ratings_history")
    op.drop_table("set_scores")
    op.drop_table("matches")
    op.drop_table("players")
    op.drop_table("tournaments")