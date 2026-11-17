from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from collectors.ubisoft import UbisoftClient, UbisoftError, sync_ubisoft_library
from database import get_db
from schemas import UbisoftConnectIn, UbisoftOut
from security import AdminUser
from settings_service import (
    SETTING_UBISOFT_LAST_SYNC,
    SETTING_UBISOFT_NAME,
    SETTING_UBISOFT_PROFILE_ID,
    SETTING_UBISOFT_REMEMBER_ME_TICKET,
    SETTING_UBISOFT_USER_ID,
    update_settings,
)

router = APIRouter(prefix="/api/ubisoft", tags=["ubisoft"])
logger = logging.getLogger(__name__)


@router.post("/connect", response_model=UbisoftOut)
def connect_ubisoft(
    payload: UbisoftConnectIn,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict:
    ticket = payload.remember_me_ticket.strip()
    if not ticket:
        raise HTTPException(status_code=422, detail="Ticket Ubisoft vide.")

    try:
        with UbisoftClient(ticket) as client:
            session = client.login()
    except UbisoftError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    update_settings(
        db,
        {
            SETTING_UBISOFT_REMEMBER_ME_TICKET: session.get("rememberMeTicket")
            or ticket,
            SETTING_UBISOFT_PROFILE_ID: session["profileId"],
            SETTING_UBISOFT_USER_ID: session.get("userId") or "",
            SETTING_UBISOFT_NAME: session.get("nameOnPlatform") or "",
        },
    )

    try:
        result = sync_ubisoft_library(db)
        return {
            "connected": True,
            "name": result.get("name") or session.get("nameOnPlatform"),
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
        }
    except UbisoftError as exc:
        logger.warning("Synchronisation Ubisoft après connexion impossible : %s", exc)
        return {
            "connected": True,
            "name": session.get("nameOnPlatform"),
            "message": f"Compte connecté, mais synchronisation impossible : {exc}",
        }


@router.post("/sync", response_model=UbisoftOut)
def sync_ubisoft(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_ubisoft_library(db)
        return {
            "connected": not result.get("skipped", False),
            "name": result.get("name"),
            "games_synced": result.get("games_synced"),
            "last_sync_at": result.get("last_sync_at"),
            "message": result.get("reason"),
        }
    except UbisoftError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/disconnect")
def disconnect_ubisoft(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    update_settings(
        db,
        {
            SETTING_UBISOFT_REMEMBER_ME_TICKET: "",
            SETTING_UBISOFT_PROFILE_ID: "",
            SETTING_UBISOFT_USER_ID: "",
            SETTING_UBISOFT_NAME: "",
            SETTING_UBISOFT_LAST_SYNC: "",
        },
    )
    return {"ok": True}
