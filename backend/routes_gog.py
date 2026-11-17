from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from collectors.gog import (
    GOG_REDIRECT_URI,
    GogClient,
    GogError,
    auth_url,
    sync_gog_library,
)
from database import get_db
from schemas import GogAuthUrlOut, GogConnectIn, GogOut
from security import AdminUser
from settings_service import (
    SETTING_GOG_LAST_SYNC,
    SETTING_GOG_REFRESH_TOKEN,
    SETTING_GOG_USER_ID,
    SETTING_GOG_USERNAME,
    update_settings,
)

router = APIRouter(prefix="/api/gog", tags=["gog"])
logger = logging.getLogger(__name__)


def _extract_code(value: str) -> str:
    """Accept a raw authorization code or the full redirect URL."""
    candidate = value.strip()
    if "code=" in candidate:
        parsed = urlparse(candidate)
        codes = parse_qs(parsed.query).get("code")
        if codes:
            return codes[0].strip()
    return candidate


@router.get("/auth-url", response_model=GogAuthUrlOut)
def read_gog_auth_url(_admin: AdminUser) -> dict:
    return {"url": auth_url(), "redirect_uri": GOG_REDIRECT_URI}


@router.post("/connect", response_model=GogOut)
def connect_gog(
    payload: GogConnectIn,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict:
    code = _extract_code(payload.code)
    if not code:
        raise HTTPException(status_code=422, detail="Code d'autorisation GOG vide.")

    try:
        with GogClient() as client:
            tokens = client.exchange_code(code)
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            user_id = str(tokens.get("user_id") or "")
            if not access_token or not refresh_token or not user_id:
                raise GogError(
                    "Réponse GOG incomplète : code expiré ou déjà utilisé."
                )
            user = client.user_data(access_token)
    except GogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    username = str(user.get("username") or "")
    update_settings(
        db,
        {
            SETTING_GOG_REFRESH_TOKEN: refresh_token,
            SETTING_GOG_USER_ID: user_id,
            SETTING_GOG_USERNAME: username,
        },
    )

    try:
        result = sync_gog_library(db)
        return {
            "connected": True,
            "name": result.get("name") or username,
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
        }
    except GogError as exc:
        logger.warning("Synchronisation GOG après connexion impossible : %s", exc)
        return {
            "connected": True,
            "name": username,
            "message": f"Compte connecté, mais synchronisation impossible : {exc}",
        }


@router.post("/sync", response_model=GogOut)
def sync_gog(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_gog_library(db)
        return {
            "connected": not result.get("skipped", False),
            "name": result.get("name"),
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
            "message": result.get("reason"),
        }
    except GogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/disconnect")
def disconnect_gog(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    update_settings(
        db,
        {
            SETTING_GOG_REFRESH_TOKEN: "",
            SETTING_GOG_USER_ID: "",
            SETTING_GOG_USERNAME: "",
            SETTING_GOG_LAST_SYNC: "",
        },
    )
    return {"ok": True}
