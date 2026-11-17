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
SETTING_HOMEPAGE_API_TOKEN = "homepage_api_token"
SETTING_INFLUX_URL = "influxdb_url"
SETTING_INFLUX_TOKEN = "influxdb_token"
SETTING_INFLUX_ORG = "influxdb_org"
SETTING_INFLUX_BUCKET = "influxdb_bucket"
SETTING_INFLUX_ENABLED = "influxdb_enabled"
SETTING_INFLUX_LAST_EXPORT = "influxdb_last_export_at"
SETTING_XBOX_CLIENT_ID = "xbox_client_id"
SETTING_XBOX_REFRESH_TOKEN = "xbox_refresh_token"
SETTING_XBOX_GAMERTAG = "xbox_gamertag"
SETTING_XBOX_XUID = "xbox_xuid"
SETTING_XBOX_GAMERSCORE = "xbox_gamerscore"
SETTING_XBOX_LAST_SYNC = "xbox_last_sync_at"
SETTING_XBOX_DEVICE_CODE = "xbox_device_code"
SETTING_XBOX_DEVICE_EXPIRES = "xbox_device_expires_at"
SETTING_XBOX_DEVICE_INTERVAL = "xbox_device_interval"
SETTING_UBISOFT_REMEMBER_ME_TICKET = "ubisoft_remember_me_ticket"
SETTING_UBISOFT_PROFILE_ID = "ubisoft_profile_id"
SETTING_UBISOFT_USER_ID = "ubisoft_user_id"
SETTING_UBISOFT_NAME = "ubisoft_name"
SETTING_UBISOFT_LAST_SYNC = "ubisoft_last_sync_at"
SETTING_GOG_REFRESH_TOKEN = "gog_refresh_token"
SETTING_GOG_USER_ID = "gog_user_id"
SETTING_GOG_USERNAME = "gog_username"
SETTING_GOG_LAST_SYNC = "gog_last_sync_at"

SECRET_SETTINGS = {
    SETTING_AGENT_API_KEY,
    SETTING_STEAM_API_KEY,
    SETTING_IGDB_CLIENT_SECRET,
    SETTING_HOMEPAGE_API_TOKEN,
    SETTING_INFLUX_TOKEN,
    SETTING_XBOX_REFRESH_TOKEN,
    SETTING_XBOX_DEVICE_CODE,
    SETTING_UBISOFT_REMEMBER_ME_TICKET,
    SETTING_GOG_REFRESH_TOKEN,
}

SETTING_DEFAULTS = {
    SETTING_AGENT_API_KEY: lambda: get_settings().agent_api_key,
    SETTING_STEAM_API_KEY: lambda: get_settings().steam_api_key,
    SETTING_STEAM_ID: lambda: get_settings().steam_id,
    SETTING_IGDB_CLIENT_ID: lambda: get_settings().igdb_client_id,
    SETTING_IGDB_CLIENT_SECRET: lambda: get_settings().igdb_client_secret,
    SETTING_TIMEZONE: lambda: get_settings().timezone,
    SETTING_HOMEPAGE_API_TOKEN: lambda: "",
    SETTING_INFLUX_URL: lambda: "",
    SETTING_INFLUX_TOKEN: lambda: "",
    SETTING_INFLUX_ORG: lambda: "",
    SETTING_INFLUX_BUCKET: lambda: "",
    SETTING_INFLUX_ENABLED: lambda: "false",
    SETTING_INFLUX_LAST_EXPORT: lambda: "",
    SETTING_XBOX_CLIENT_ID: lambda: get_settings().xbox_client_id,
    SETTING_XBOX_REFRESH_TOKEN: lambda: "",
    SETTING_XBOX_GAMERTAG: lambda: "",
    SETTING_XBOX_XUID: lambda: "",
    SETTING_XBOX_GAMERSCORE: lambda: "0",
    SETTING_XBOX_LAST_SYNC: lambda: "",
    SETTING_XBOX_DEVICE_CODE: lambda: "",
    SETTING_XBOX_DEVICE_EXPIRES: lambda: "",
    SETTING_XBOX_DEVICE_INTERVAL: lambda: "5",
    SETTING_UBISOFT_REMEMBER_ME_TICKET: lambda: "",
    SETTING_UBISOFT_PROFILE_ID: lambda: "",
    SETTING_UBISOFT_USER_ID: lambda: "",
    SETTING_UBISOFT_NAME: lambda: "",
    SETTING_UBISOFT_LAST_SYNC: lambda: "",
    SETTING_GOG_REFRESH_TOKEN: lambda: "",
    SETTING_GOG_USER_ID: lambda: "",
    SETTING_GOG_USERNAME: lambda: "",
    SETTING_GOG_LAST_SYNC: lambda: "",
}


@dataclass(frozen=True)
class IntegrationSettings:
    agent_api_key: str
    steam_api_key: str
    steam_id: str
    igdb_client_id: str
    igdb_client_secret: str
    timezone: str
    homepage_api_token: str
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str
    influxdb_enabled: bool
    xbox_client_id: str
    xbox_refresh_token: str
    xbox_gamertag: str
    xbox_xuid: str
    xbox_gamerscore: int
    ubisoft_remember_me_ticket: str
    ubisoft_profile_id: str
    ubisoft_user_id: str
    ubisoft_name: str
    gog_refresh_token: str
    gog_user_id: str
    gog_username: str

    @property
    def steam_configured(self) -> bool:
        return bool(self.steam_api_key and self.steam_id)

    @property
    def igdb_configured(self) -> bool:
        return bool(self.igdb_client_id and self.igdb_client_secret)

    @property
    def influxdb_configured(self) -> bool:
        return bool(
            self.influxdb_url
            and self.influxdb_token
            and self.influxdb_org
            and self.influxdb_bucket
        )

    @property
    def xbox_connected(self) -> bool:
        return bool(self.xbox_client_id and self.xbox_refresh_token and self.xbox_xuid)

    @property
    def ubisoft_connected(self) -> bool:
        return bool(
            self.ubisoft_remember_me_ticket
            and self.ubisoft_profile_id
            and self.ubisoft_user_id
        )

    @property
    def gog_connected(self) -> bool:
        return bool(self.gog_refresh_token and self.gog_user_id)


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


def _int_setting(db: Session, key: str) -> int:
    try:
        return int(get_setting(db, key, "0") or 0)
    except ValueError:
        return 0


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
        homepage_api_token=get_setting(db, SETTING_HOMEPAGE_API_TOKEN, ""),
        influxdb_url=get_setting(db, SETTING_INFLUX_URL, ""),
        influxdb_token=get_setting(db, SETTING_INFLUX_TOKEN, ""),
        influxdb_org=get_setting(db, SETTING_INFLUX_ORG, ""),
        influxdb_bucket=get_setting(db, SETTING_INFLUX_BUCKET, ""),
        influxdb_enabled=get_setting(db, SETTING_INFLUX_ENABLED, "false").lower()
        == "true",
        xbox_client_id=get_setting(
            db, SETTING_XBOX_CLIENT_ID, get_settings().xbox_client_id
        ),
        xbox_refresh_token=get_setting(db, SETTING_XBOX_REFRESH_TOKEN, ""),
        xbox_gamertag=get_setting(db, SETTING_XBOX_GAMERTAG, ""),
        xbox_xuid=get_setting(db, SETTING_XBOX_XUID, ""),
        xbox_gamerscore=_int_setting(db, SETTING_XBOX_GAMERSCORE),
        ubisoft_remember_me_ticket=get_setting(
            db, SETTING_UBISOFT_REMEMBER_ME_TICKET, ""
        ),
        ubisoft_profile_id=get_setting(db, SETTING_UBISOFT_PROFILE_ID, ""),
        ubisoft_user_id=get_setting(db, SETTING_UBISOFT_USER_ID, ""),
        ubisoft_name=get_setting(db, SETTING_UBISOFT_NAME, ""),
        gog_refresh_token=get_setting(db, SETTING_GOG_REFRESH_TOKEN, ""),
        gog_user_id=get_setting(db, SETTING_GOG_USER_ID, ""),
        gog_username=get_setting(db, SETTING_GOG_USERNAME, ""),
    )


def get_agent_api_key(db: Session) -> str:
    return get_setting(
        db, SETTING_AGENT_API_KEY, get_settings().agent_api_key
    ).strip()


def get_homepage_api_token(db: Session) -> str:
    return get_setting(db, SETTING_HOMEPAGE_API_TOKEN, "").strip()


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
