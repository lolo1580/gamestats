from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HeartbeatGameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    process: str | None = Field(default=None, max_length=255)
    steam_app_id: int | None = Field(default=None, ge=1)


class HeartbeatIn(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    hostname: str | None = Field(default=None, max_length=255)
    games: list[HeartbeatGameIn] = Field(default_factory=list, max_length=64)
    captured_at: datetime | None = None


class ActiveSessionOut(BaseModel):
    id: int
    game_id: int
    game_name: str
    started_at: datetime


class HeartbeatOut(BaseModel):
    accepted: bool
    received_at: datetime
    active_sessions: list[ActiveSessionOut]


class GameOut(BaseModel):
    id: int
    name: str
    steam_app_id: int | None
    cover_url: str | None
    genres: list[str]
    steam_playtime_minutes: int
    playtime_2weeks_minutes: int
    achievements_total: int
    achievements_unlocked: int
    last_played_at: datetime | None


class TopGameOut(GameOut):
    tracked_seconds: int


class SessionOut(BaseModel):
    id: int
    game_id: int
    game_name: str
    cover_url: str | None
    source: str
    agent_id: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    is_live: bool


class SummaryOut(BaseModel):
    today_seconds: int
    week_seconds: int
    total_seconds: int
    sessions_week: int
    distinct_games_week: int
    active_count: int
    library_count: int
    agents_online: int
    agents_total: int


class HeatmapCellOut(BaseModel):
    weekday: int
    hour: int
    seconds: int


class HeatmapOut(BaseModel):
    days: int
    max_seconds: int
    cells: list[HeatmapCellOut]


class DailyPointOut(BaseModel):
    date: str
    seconds: int


class DailyStatsOut(BaseModel):
    days: int
    max_seconds: int
    items: list[DailyPointOut]


class SyncResultOut(BaseModel):
    skipped: bool = False
    reason: str | None = None
    created: int | None = None
    updated: int | None = None
    sessions_created: int | None = None
    achievements_synced: int | None = None
    enriched: int | None = None
