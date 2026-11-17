from __future__ import annotations

import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import AgentKeyOut, SettingsOut, SettingsUpdate
from security import AdminUser
from settings_service import (
    SETTING_AGENT_API_KEY,
    SETTING_IGDB_CLIENT_ID,
    SETTING_IGDB_CLIENT_SECRET,
    SETTING_STEAM_API_KEY,
    SETTING_STEAM_ID,
    SETTING_TIMEZONE,
    get_integration_settings,
    get_setting,
    mask_secret,
    update_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _settings_out(db: Session) -> SettingsOut:
    integration = get_integration_settings(db)
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
