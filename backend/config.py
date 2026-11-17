from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration du backend, chargée depuis l'environnement / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GameStats"
    database_url: str = "sqlite:///./data/gamestats.db"
    agent_api_key: str = "change-me"
    timezone: str = "Europe/Paris"
    cors_origins: str = "*"
    log_level: str = "INFO"

    steam_api_key: str = ""
    steam_id: str = ""

    igdb_client_id: str = ""
    igdb_client_secret: str = ""

    scheduler_enabled: bool = True
    agent_stale_seconds: int = 180
    steam_sync_minutes: int = 15
    igdb_sync_minutes: int = 60
    influx_export_minutes: int = 15
    xbox_sync_minutes: int = 30
    xbox_client_id: str = ""
    ubisoft_sync_minutes: int = 60
    gog_sync_minutes: int = 60
    igdb_enrich_limit: int = 8
    steam_achievement_limit: int = 8
    session_days: int = 7
    cookie_secure: bool = False

    @property
    def steam_configured(self) -> bool:
        return bool(self.steam_api_key and self.steam_id)

    @property
    def igdb_configured(self) -> bool:
        return bool(self.igdb_client_id and self.igdb_client_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
