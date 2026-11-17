from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from config import get_settings
from models import AppSetting

SETTING_AGENT_API_KEY = "agent_api_key"
SETTING_STEAM_API_KEY = "steam_api_key"
SETTING_STEAM_ID = "steam_id"
SETTING_IGDB_CLIENT_ID = "igdb_client_id"
SETTING_IGDB_CLIENT_SECRET = "igdb_client_secret"
SETTING_TIMEZONE = "timezone"

SECRET_SETTINGS = {
    SETTING_AGENT_API_KEY,
    SETTING_STEAM_API_KEY,
    SETTING_IGDB_CLIENT_SECRET,
}

SETTING_DEFAULTS = {
    SETTING_AGENT_API_KEY: lambda: get_settings().agent_api_key,
    SETTING_STEAM_API_KEY: lambda: get_settings().steam_api_key,
    SETTING_STEAM_ID: lambda: get_settings().steam_id,
    SETTING_IGDB_CLIENT_ID: lambda: get_settings().igdb_client_id,
    SETTING_IGDB_CLIENT_SECRET: lambda: get_settings().igdb_client_secret,
    SETTING_TIMEZONE: lambda: get_settings().timezone,
}


@dataclass(frozen=True)
class IntegrationSettings:
    agent_api_key: str
    steam_api_key: str
    steam_id: str
    igdb_client_id: str
    igdb_client_secret: str
    timezone: str

    @property
    def steam_configured(self) -> bool:
        return bool(self.steam_api_key and self.steam_id)

    @property
    def igdb_configured(self) -> bool:
        return bool(self.igdb_client_id and self.igdb_client_secret)


def ensure_default_settings(db: Session) -> None:
    """Seed settings from environment values without overwriting user choices."""

    created = False
    for key, factory in SETTING_DEFAULTS.items():
        if db.get(AppSetting, key) is None:
            db.add(AppSetting(key=key, value=factory()))
            created = True
    if created:
        db.commit()


def get_setting(db: Session, key: str, default: str | None = None) -> str:
    row = db.get(AppSetting, key)
    if row is None:
        return default or ""
    return row.value or ""


def get_integration_settings(db: Session) -> IntegrationSettings:
    settings = get_settings()
    return IntegrationSettings(
        agent_api_key=get_setting(db, SETTING_AGENT_API_KEY, settings.agent_api_key),
        steam_api_key=get_setting(db, SETTING_STEAM_API_KEY, settings.steam_api_key),
        steam_id=get_setting(db, SETTING_STEAM_ID, settings.steam_id),
        igdb_client_id=get_setting(db, SETTING_IGDB_CLIENT_ID, settings.igdb_client_id),
        igdb_client_secret=get_setting(
            db, SETTING_IGDB_CLIENT_SECRET, settings.igdb_client_secret
        ),
        timezone=get_setting(db, SETTING_TIMEZONE, settings.timezone),
    )


def get_agent_api_key(db: Session) -> str:
    return get_setting(
        db, SETTING_AGENT_API_KEY, get_settings().agent_api_key
    ).strip()


def get_timezone_name(db: Session) -> str:
    name = get_setting(db, SETTING_TIMEZONE, get_settings().timezone)
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return name


def update_settings(db: Session, updates: dict[str, str | None]) -> None:
    for key, value in updates.items():
        if value is None:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"
