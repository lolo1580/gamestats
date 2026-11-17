from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from collectors.epic import (
    EpicClient,
    EpicError,
    auth_url,
    redirect_uri,
    sync_epic_library,
)
from database import get_db
from schemas import EpicAuthUrlOut, EpicConnectIn, EpicOut
from security import AdminUser
from settings_service import (
    SETTING_EPIC_ACCOUNT_ID,
    SETTING_EPIC_DISPLAY_NAME,
    SETTING_EPIC_LAST_SYNC,
    SETTING_EPIC_REFRESH_TOKEN,
    update_settings,
)

router = APIRouter(prefix="/api/epic", tags=["epic"])
logger = logging.getLogger(__name__)


def _extract_code(value: str) -> str:
    """Accept a raw code, a redirect URL, or the JSON page shown by Epic."""
    candidate = value.strip()
    if not candidate:
        return ""
    if candidate.startswith("{"):
        try:
            payload = json.loads(candidate)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            for key in ("authorizationCode", "exchangeCode", "code"):
                code = payload.get(key)
                if isinstance(code, str) and code.strip():
                    return code.strip()
    if "code=" in candidate:
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query)
        for key in ("authorizationCode", "exchangeCode", "code"):
            values = query.get(key)
            if values and values[0].strip():
                return values[0].strip()
    return candidate


@router.get("/auth-url", response_model=EpicAuthUrlOut)
def read_epic_auth_url(_admin: AdminUser) -> dict:
    return {"url": auth_url(), "redirect_uri": redirect_uri()}


@router.post("/connect", response_model=EpicOut)
def connect_epic(
    payload: EpicConnectIn,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict:
    code = _extract_code(payload.code)
    if not code:
        raise HTTPException(
            status_code=422, detail="Code d'autorisation Epic Games vide."
        )

    try:
        with EpicClient() as client:
            tokens = client.exchange_code(code)
    except EpicError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    refresh_token = tokens.get("refresh_token")
    account_id = str(tokens.get("account_id") or "")
    display_name = str(tokens.get("displayName") or "")
    if not refresh_token or not account_id:
        raise HTTPException(
            status_code=502,
            detail="Réponse Epic Games incomplète : code expiré ou déjà utilisé.",
        )

    update_settings(
        db,
        {
            SETTING_EPIC_REFRESH_TOKEN: refresh_token,
            SETTING_EPIC_ACCOUNT_ID: account_id,
            SETTING_EPIC_DISPLAY_NAME: display_name,
        },
    )

    try:
        result = sync_epic_library(db)
        return {
            "connected": True,
            "name": result.get("name") or display_name,
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
        }
    except EpicError as exc:
        logger.warning(
            "Synchronisation Epic Games après connexion impossible : %s", exc
        )
        return {
            "connected": True,
            "name": display_name,
            "message": f"Compte connecté, mais synchronisation impossible : {exc}",
        }


@router.post("/sync", response_model=EpicOut)
def sync_epic(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_epic_library(db)
        return {
            "connected": not result.get("skipped", False),
            "name": result.get("name"),
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
            "message": result.get("reason"),
        }
    except EpicError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/disconnect")
def disconnect_epic(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    update_settings(
        db,
        {
            SETTING_EPIC_REFRESH_TOKEN: "",
            SETTING_EPIC_ACCOUNT_ID: "",
            SETTING_EPIC_DISPLAY_NAME: "",
            SETTING_EPIC_LAST_SYNC: "",
        },
    )
    return {"ok": True}
