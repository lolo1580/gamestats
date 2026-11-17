from __future__ import annotations

import secrets
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import AgentKeyOut, HomepageTokenOut, SettingsOut, SettingsUpdate
from security import AdminUser
from settings_service import (
    SETTING_AGENT_API_KEY,
    SETTING_HOMEPAGE_API_TOKEN,
    SETTING_GOG_LAST_SYNC,
    SETTING_GOG_REFRESH_TOKEN,
    SETTING_GOG_USERNAME,
    SETTING_IGDB_CLIENT_ID,
    SETTING_IGDB_CLIENT_SECRET,
    SETTING_INFLUX_BUCKET,
    SETTING_INFLUX_ENABLED,
    SETTING_INFLUX_LAST_EXPORT,
    SETTING_INFLUX_ORG,
    SETTING_INFLUX_TOKEN,
    SETTING_INFLUX_URL,
    SETTING_STEAM_API_KEY,
    SETTING_STEAM_ID,
    SETTING_TIMEZONE,
    SETTING_UBISOFT_LAST_SYNC,
    SETTING_UBISOFT_NAME,
    SETTING_UBISOFT_REMEMBER_ME_TICKET,
    SETTING_XBOX_CLIENT_ID,
    SETTING_XBOX_GAMERSCORE,
    SETTING_XBOX_GAMERTAG,
    SETTING_XBOX_LAST_SYNC,
    SETTING_XBOX_REFRESH_TOKEN,
    SETTING_XBOX_XUID,
    get_integration_settings,
    get_setting,
    mask_secret,
    update_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _settings_out(db: Session) -> SettingsOut:
    integration = get_integration_settings(db)
    last_export = get_setting(db, SETTING_INFLUX_LAST_EXPORT) or None
    return SettingsOut(
        steam_api_key_hint=mask_secret(integration.steam_api_key),
        steam_api_key_set=bool(integration.steam_api_key),
        steam_id=integration.steam_id,
        igdb_client_id=integration.igdb_client_id,
        igdb_client_secret_hint=mask_secret(integration.igdb_client_secret),
        igdb_client_secret_set=bool(integration.igdb_client_secret),
        agent_api_key_hint=mask_secret(integration.agent_api_key),
        agent_api_key_set=bool(integration.agent_api_key),
        timezone=integration.timezone,
        steam_configured=integration.steam_configured,
        igdb_configured=integration.igdb_configured,
        homepage_api_token_hint=mask_secret(integration.homepage_api_token),
        homepage_api_token_set=bool(integration.homepage_api_token),
        influxdb_url=integration.influxdb_url,
        influxdb_token_hint=mask_secret(integration.influxdb_token),
        influxdb_token_set=bool(integration.influxdb_token),
        influxdb_org=integration.influxdb_org,
        influxdb_bucket=integration.influxdb_bucket,
        influxdb_enabled=integration.influxdb_enabled,
        influxdb_configured=integration.influxdb_configured,
        influxdb_last_export_at=last_export,
        xbox_client_id=integration.xbox_client_id,
        xbox_refresh_token_hint=mask_secret(integration.xbox_refresh_token),
        xbox_refresh_token_set=bool(integration.xbox_refresh_token),
        xbox_gamertag=integration.xbox_gamertag,
        xbox_gamerscore=integration.xbox_gamerscore,
        xbox_connected=integration.xbox_connected,
        xbox_last_sync_at=get_setting(db, SETTING_XBOX_LAST_SYNC) or None,
        ubisoft_remember_me_ticket_hint=mask_secret(
            integration.ubisoft_remember_me_ticket
        ),
        ubisoft_remember_me_ticket_set=bool(
            integration.ubisoft_remember_me_ticket
        ),
        ubisoft_name=integration.ubisoft_name,
        ubisoft_connected=integration.ubisoft_connected,
        ubisoft_last_sync_at=get_setting(db, SETTING_UBISOFT_LAST_SYNC) or None,
        gog_refresh_token_hint=mask_secret(integration.gog_refresh_token),
        gog_refresh_token_set=bool(integration.gog_refresh_token),
        gog_username=integration.gog_username,
        gog_connected=integration.gog_connected,
        gog_last_sync_at=get_setting(db, SETTING_GOG_LAST_SYNC) or None,
    )


@router.get("", response_model=SettingsOut)
def read_settings(_admin: AdminUser, db: Session = Depends(get_db)) -> SettingsOut:
    return _settings_out(db)


@router.patch("", response_model=SettingsOut)
def write_settings(
    payload: SettingsUpdate,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> SettingsOut:
    fields = payload.model_fields_set
    updates: dict[str, str | None] = {}

    if "steam_api_key" in fields:
        updates[SETTING_STEAM_API_KEY] = (payload.steam_api_key or "").strip()
    if "steam_id" in fields:
        steam_id = (payload.steam_id or "").strip()
        if steam_id and not steam_id.isdigit():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le SteamID64 doit être composé uniquement de chiffres.",
            )
        updates[SETTING_STEAM_ID] = steam_id
    if "igdb_client_id" in fields:
        updates[SETTING_IGDB_CLIENT_ID] = (payload.igdb_client_id or "").strip()
    if "igdb_client_secret" in fields:
        updates[SETTING_IGDB_CLIENT_SECRET] = (
            payload.igdb_client_secret or ""
        ).strip()
    if "agent_api_key" in fields:
        agent_key = (payload.agent_api_key or "").strip()
        if len(agent_key) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clé agent doit contenir au moins 8 caractères.",
            )
        updates[SETTING_AGENT_API_KEY] = agent_key
    if "timezone" in fields:
        timezone = (payload.timezone or "").strip()
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Fuseau horaire invalide.",
            ) from exc
        updates[SETTING_TIMEZONE] = timezone
    if "homepage_api_token" in fields:
        token = (payload.homepage_api_token or "").strip()
        if token and len(token) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le token Homepage doit contenir au moins 8 caractères.",
            )
        updates[SETTING_HOMEPAGE_API_TOKEN] = token
    if "influxdb_url" in fields:
        url = (payload.influxdb_url or "").strip().rstrip("/")
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="URL InfluxDB invalide (http:// ou https:// attendu).",
                )
        updates[SETTING_INFLUX_URL] = url
    if "influxdb_token" in fields:
        updates[SETTING_INFLUX_TOKEN] = (payload.influxdb_token or "").strip()
    if "influxdb_org" in fields:
        updates[SETTING_INFLUX_ORG] = (payload.influxdb_org or "").strip()
    if "influxdb_bucket" in fields:
        updates[SETTING_INFLUX_BUCKET] = (payload.influxdb_bucket or "").strip()
    if "influxdb_enabled" in fields:
        updates[SETTING_INFLUX_ENABLED] = (
            "true" if payload.influxdb_enabled else "false"
        )
    if "xbox_client_id" in fields:
        updates[SETTING_XBOX_CLIENT_ID] = (payload.xbox_client_id or "").strip()
    if "xbox_refresh_token" in fields:
        token = (payload.xbox_refresh_token or "").strip()
        updates[SETTING_XBOX_REFRESH_TOKEN] = token
        if not token:
            updates[SETTING_XBOX_XUID] = ""
            updates[SETTING_XBOX_GAMERTAG] = ""
            updates[SETTING_XBOX_GAMERSCORE] = "0"

    current = get_integration_settings(db)
    prospective_url = updates.get(SETTING_INFLUX_URL, current.influxdb_url)
    prospective_token = updates.get(SETTING_INFLUX_TOKEN, current.influxdb_token)
    prospective_org = updates.get(SETTING_INFLUX_ORG, current.influxdb_org)
    prospective_bucket = updates.get(SETTING_INFLUX_BUCKET, current.influxdb_bucket)
    enabled = updates.get(SETTING_INFLUX_ENABLED, str(current.influxdb_enabled).lower()) == "true"
    if enabled and not all(
        [prospective_url, prospective_token, prospective_org, prospective_bucket]
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Renseignez l'URL, le token, l'organisation et le bucket avant d'activer InfluxDB.",
        )

    update_settings(db, updates)
    return _settings_out(db)


@router.get("/agent-key", response_model=AgentKeyOut)
def reveal_agent_key(
    _admin: AdminUser, db: Session = Depends(get_db)
) -> AgentKeyOut:
    value = get_setting(db, SETTING_AGENT_API_KEY)
    if not value:
        raise HTTPException(status_code=404, detail="Aucune clé agent configurée.")
    return AgentKeyOut(agent_api_key=value)


@router.post("/agent-key/rotate", response_model=AgentKeyOut)
def rotate_agent_key(
    _admin: AdminUser, db: Session = Depends(get_db)
) -> AgentKeyOut:
    value = secrets.token_urlsafe(32)
    update_settings(db, {SETTING_AGENT_API_KEY: value})
    return AgentKeyOut(agent_api_key=value)


@router.get("/homepage-token", response_model=HomepageTokenOut)
def reveal_homepage_token(
    _admin: AdminUser, db: Session = Depends(get_db)
) -> HomepageTokenOut:
    value = get_setting(db, SETTING_HOMEPAGE_API_TOKEN)
    if not value:
        raise HTTPException(
            status_code=404, detail="Aucun token Homepage configuré."
        )
    return HomepageTokenOut(homepage_api_token=value)


@router.post("/homepage-token/rotate", response_model=HomepageTokenOut)
def rotate_homepage_token(
    _admin: AdminUser, db: Session = Depends(get_db)
) -> HomepageTokenOut:
    value = secrets.token_urlsafe(32)
    update_settings(db, {SETTING_HOMEPAGE_API_TOKEN: value})
    return HomepageTokenOut(homepage_api_token=value)
