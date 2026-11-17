from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    role: Literal["admin", "viewer"]
    is_active: bool
    locale: str
    created_at: datetime
    last_login_at: datetime | None


class AuthStatusOut(BaseModel):
    needs_setup: bool
    authenticated: bool
    user: UserOut | None


class LoginIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class SetupIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ProfileUpdateIn(BaseModel):
    locale: Literal["fr", "en"] | None = None


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["admin", "viewer"] = "viewer"


class UserUpdateIn(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    role: Literal["admin", "viewer"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)


class SettingsOut(BaseModel):
    steam_api_key_hint: str
    steam_api_key_set: bool
    steam_id: str
    igdb_client_id: str
    igdb_client_secret_hint: str
    igdb_client_secret_set: bool
    agent_api_key_hint: str
    agent_api_key_set: bool
    timezone: str
    steam_configured: bool
    igdb_configured: bool
    homepage_api_token_hint: str
    homepage_api_token_set: bool
    influxdb_url: str
    influxdb_token_hint: str
    influxdb_token_set: bool
    influxdb_org: str
    influxdb_bucket: str
    influxdb_enabled: bool
    influxdb_configured: bool
    influxdb_last_export_at: str | None
    xbox_client_id: str
    xbox_refresh_token_hint: str
    xbox_refresh_token_set: bool
    xbox_gamertag: str
    xbox_gamerscore: int
    xbox_connected: bool
    xbox_last_sync_at: str | None
    ubisoft_remember_me_ticket_hint: str
    ubisoft_remember_me_ticket_set: bool
    ubisoft_name: str
    ubisoft_connected: bool
    ubisoft_last_sync_at: str | None
    gog_refresh_token_hint: str
    gog_refresh_token_set: bool
    gog_username: str
    gog_connected: bool
    gog_last_sync_at: str | None


class SettingsUpdate(BaseModel):
    steam_api_key: str | None = None
    steam_id: str | None = None
    igdb_client_id: str | None = None
    igdb_client_secret: str | None = None
    agent_api_key: str | None = None
    timezone: str | None = None
    homepage_api_token: str | None = None
    influxdb_url: str | None = None
    influxdb_token: str | None = None
    influxdb_org: str | None = None
    influxdb_bucket: str | None = None
    influxdb_enabled: bool | None = None
    xbox_client_id: str | None = None
    xbox_refresh_token: str | None = None


class AgentKeyOut(BaseModel):
    agent_api_key: str


class HomepageTokenOut(BaseModel):
    homepage_api_token: str


class InfluxExportOut(BaseModel):
    skipped: bool = False
    reason: str | None = None
    sessions_exported: int | None = None
    points_written: int | None = None
    last_export_at: str | None = None


class XboxDeviceCodeOut(BaseModel):
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class XboxPollOut(BaseModel):
    status: Literal["pending", "connected", "expired", "error"]
    message: str | None = None
    gamertag: str | None = None
    gamerscore: int | None = None
    titles_synced: int | None = None


class XboxSyncOut(BaseModel):
    skipped: bool = False
    reason: str | None = None
    titles_synced: int | None = None
    gamerscore: int | None = None
    last_sync_at: str | None = None


class UbisoftConnectIn(BaseModel):
    remember_me_ticket: str = Field(min_length=10, max_length=4096)


class UbisoftOut(BaseModel):
    connected: bool
    name: str | None = None
    games_synced: int | None = None
    last_sync_at: str | None = None
    message: str | None = None


class GogConnectIn(BaseModel):
    code: str = Field(min_length=8, max_length=4096)


class GogAuthUrlOut(BaseModel):
    url: str
    redirect_uri: str


class GogOut(BaseModel):
    connected: bool
    name: str | None = None
    games_synced: int | None = None
    last_sync_at: str | None = None
    message: str | None = None


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
    xbox_title_id: str | None
    cover_url: str | None
    genres: list[str]
    steam_playtime_minutes: int
    playtime_2weeks_minutes: int
    achievements_total: int
    achievements_unlocked: int
    last_played_at: datetime | None
    xbox_achievements_total: int
    xbox_achievements_unlocked: int
    xbox_gamerscore: int
    xbox_gamerscore_total: int
    xbox_last_played_at: datetime | None
    ubisoft_space_id: str | None
    ubisoft_sessions_count: int
    ubisoft_first_played_at: datetime | None
    ubisoft_last_played_at: datetime | None
    gog_product_id: int | None
    gog_achievements_total: int
    gog_achievements_unlocked: int


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
