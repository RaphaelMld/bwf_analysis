from datetime import date, datetime
from sqlalchemy import (
    BigInteger, Date, DateTime, Float, ForeignKey,
    Integer, SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bwf_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    bwf_code: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    prize_money: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    matches: Mapped[list["Match"]] = relationship(back_populates="tournament")
    scraping_jobs: Mapped[list["ScrapingJob"]] = relationship(back_populates="tournament")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bwf_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    ratings: Mapped[list["RatingHistory"]] = relationship(back_populates="player")
    rankings: Mapped[list["BwfRanking"]] = relationship(back_populates="player")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("bwf_match_id", name="uq_matches_bwf_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bwf_match_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
    discipline: Mapped[str] = mapped_column(String(2), nullable=False)  # MS ou WS
    round_name: Mapped[str | None] = mapped_column(String(50))
    match_time_utc: Mapped[datetime | None] = mapped_column(DateTime)
    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    player2_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    player1_seed: Mapped[int | None] = mapped_column(SmallInteger)
    player2_seed: Mapped[int | None] = mapped_column(SmallInteger)
    winner: Mapped[int | None] = mapped_column(SmallInteger)  # 1 ou 2
    score_status: Mapped[int] = mapped_column(SmallInteger, default=0)  # 0=Normal
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tournament: Mapped["Tournament"] = relationship(back_populates="matches")
    player1: Mapped["Player"] = relationship(foreign_keys=[player1_id])
    player2: Mapped["Player"] = relationship(foreign_keys=[player2_id])
    set_scores: Mapped[list["SetScore"]] = relationship(back_populates="match")
    ratings_history: Mapped[list["RatingHistory"]] = relationship(back_populates="after_match")


class SetScore(Base):
    __tablename__ = "set_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    set_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_player1: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score_player2: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    match: Mapped["Match"] = relationship(back_populates="set_scores")


class RatingHistory(Base):
    __tablename__ = "ratings_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    discipline: Mapped[str] = mapped_column(String(2), nullable=False)
    rating_type: Mapped[str] = mapped_column(String(20), nullable=False)  # elo, bradley_terry
    rating_value: Mapped[float] = mapped_column(Float, nullable=False)
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    after_match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    player: Mapped["Player"] = relationship(back_populates="ratings")
    after_match: Mapped["Match | None"] = relationship(back_populates="ratings_history")


class BwfRanking(Base):
    __tablename__ = "bwf_rankings"
    __table_args__ = (
        UniqueConstraint("player_id", "discipline", "week_date", name="uq_ranking_player_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    discipline: Mapped[str] = mapped_column(String(2), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[float] = mapped_column(Float, nullable=False)
    week_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    player: Mapped["Player"] = relationship(back_populates="rankings")


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tournament: Mapped["Tournament"] = relationship(back_populates="scraping_jobs")