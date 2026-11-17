from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    name_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    steam_app_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    xbox_title_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    ubisoft_space_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    gog_product_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    epic_catalog_item_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    igdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    igdb_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steam_playtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    steam_playtime_2weeks: Mapped[int] = mapped_column(Integer, default=0)
    achievements_total: Mapped[int] = mapped_column(Integer, default=0)
    achievements_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    achievements_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_steam_play_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    xbox_achievements_total: Mapped[int] = mapped_column(Integer, default=0)
    xbox_achievements_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    xbox_gamerscore: Mapped[int] = mapped_column(Integer, default=0)
    xbox_gamerscore_total: Mapped[int] = mapped_column(Integer, default=0)
    xbox_last_played_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ubisoft_sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    ubisoft_first_played_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ubisoft_last_played_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gog_achievements_total: Mapped[int] = mapped_column(Integer, default=0)
    gog_achievements_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    gog_achievements_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    epic_namespace: Mapped[str | None] = mapped_column(String(64), nullable=True)
    epic_achievements_total: Mapped[int] = mapped_column(Integer, default=0)
    epic_achievements_unlocked: Mapped[int] = mapped_column(Integer, default=0)
    epic_achievements_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mobygames_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    mobygames_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mobygames_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mobygames_num_votes: Mapped[int] = mapped_column(Integer, default=0)
    mobygames_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opencritic_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    opencritic_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    opencritic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    opencritic_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    opencritic_reviews: Mapped[int] = mapped_column(Integer, default=0)
    opencritic_recommended: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opencritic_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hltb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    hltb_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hltb_main_minutes: Mapped[int] = mapped_column(Integer, default=0)
    hltb_main_extra_minutes: Mapped[int] = mapped_column(Integer, default=0)
    hltb_completionist_minutes: Mapped[int] = mapped_column(Integer, default=0)
    hltb_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list[GameSession]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[PlaytimeSnapshot]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GameSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_game_started", "game_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(16), default="agent")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    game: Mapped[Game] = relationship(back_populates="sessions")


class PlaytimeSnapshot(Base):
    __tablename__ = "playtime_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    total_minutes: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    game: Mapped[Game] = relationship(back_populates="snapshots")


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    locale: Mapped[str] = mapped_column(String(8), default="fr")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
