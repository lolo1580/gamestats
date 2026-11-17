from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collectors.xbox import (
    XboxError,
    authenticate_xbox,
    device_code_expiry,
    poll_device_code,
    start_device_code,
    sync_xbox_library,
)
from database import get_db
from schemas import XboxDeviceCodeOut, XboxPollOut, XboxSyncOut
from security import AdminUser
from settings_service import (
    SETTING_XBOX_CLIENT_ID,
    SETTING_XBOX_DEVICE_CODE,
    SETTING_XBOX_DEVICE_EXPIRES,
    SETTING_XBOX_DEVICE_INTERVAL,
    SETTING_XBOX_GAMERSCORE,
    SETTING_XBOX_GAMERTAG,
    SETTING_XBOX_LAST_SYNC,
    SETTING_XBOX_REFRESH_TOKEN,
    SETTING_XBOX_XUID,
    get_integration_settings,
    get_setting,
    update_settings,
)
from utils import ensure_utc, utcnow

router = APIRouter(prefix="/api/xbox", tags=["xbox"])
logger = logging.getLogger(__name__)


def _clear_device_code(db: Session) -> None:
    update_settings(
        db,
        {
            SETTING_XBOX_DEVICE_CODE: "",
            SETTING_XBOX_DEVICE_EXPIRES: "",
        },
    )


@router.post("/device-code", response_model=XboxDeviceCodeOut)
def begin_device_code(
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> XboxDeviceCodeOut:
    integration = get_integration_settings(db)
    if not integration.xbox_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Renseignez et enregistrez le Client ID Xbox avant de vous connecter.",
        )
    try:
        data = start_device_code(integration.xbox_client_id)
    except XboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    expires_at = device_code_expiry(int(data.get("expires_in", 900)))
    update_settings(
        db,
        {
            SETTING_XBOX_DEVICE_CODE: data["device_code"],
            SETTING_XBOX_DEVICE_EXPIRES: expires_at.isoformat(),
            SETTING_XBOX_DEVICE_INTERVAL: str(data.get("interval", 5)),
        },
    )
    return XboxDeviceCodeOut(
        user_code=data["user_code"],
        verification_uri=data.get(
            "verification_uri", "https://microsoft.com/link"
        ),
        expires_in=int(data.get("expires_in", 900)),
        interval=max(5, int(data.get("interval", 5))),
    )


@router.post("/device-code/poll", response_model=XboxPollOut)
def poll_connection(
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> XboxPollOut:
    integration = get_integration_settings(db)
    device_code = get_setting(db, SETTING_XBOX_DEVICE_CODE)
    expires_raw = get_setting(db, SETTING_XBOX_DEVICE_EXPIRES)
    if not integration.xbox_client_id or not device_code:
        return XboxPollOut(status="error", message="Aucune connexion Xbox en cours.")

    try:
        expires = ensure_utc(datetime.fromisoformat(expires_raw)) if expires_raw else None
    except ValueError:
        expires = None
    if expires is None or expires <= utcnow():
        _clear_device_code(db)
        return XboxPollOut(status="expired", message="Le code a expiré.")

    try:
        result = poll_device_code(integration.xbox_client_id, device_code)
    except XboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result["status"] == "pending":
        return XboxPollOut(status="pending")
    if result["status"] == "expired":
        _clear_device_code(db)
        return XboxPollOut(status="expired", message="Le code a expiré.")
    if result["status"] == "error":
        _clear_device_code(db)
        return XboxPollOut(status="error", message=result.get("message"))

    tokens = result.get("tokens") or {}
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token or not refresh_token:
        _clear_device_code(db)
        return XboxPollOut(
            status="error", message="Microsoft n'a pas renvoyé de token Xbox."
        )

    try:
        auth = authenticate_xbox(access_token)
    except XboxError as exc:
        return XboxPollOut(status="error", message=str(exc))

    update_settings(
        db,
        {
            SETTING_XBOX_REFRESH_TOKEN: refresh_token,
            SETTING_XBOX_XUID: auth["xuid"],
            SETTING_XBOX_DEVICE_CODE: "",
            SETTING_XBOX_DEVICE_EXPIRES: "",
        },
    )

    sync_message: str | None = None
    try:
        sync_result = sync_xbox_library(db)
    except XboxError as exc:
        sync_message = f"Compte connecté, mais synchronisation impossible : {exc}"
        logger.warning("Synchronisation Xbox après connexion impossible : %s", exc)
        sync_result = {}

    return XboxPollOut(
        status="connected",
        message=sync_message,
        gamertag=sync_result.get("gamertag")
        or get_setting(db, SETTING_XBOX_GAMERTAG)
        or None,
        gamerscore=sync_result.get("gamerscore")
        if sync_result
        else int(get_setting(db, SETTING_XBOX_GAMERSCORE) or 0),
        titles_synced=sync_result.get("titles_synced"),
    )


@router.post("/sync", response_model=XboxSyncOut)
def sync_now(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        result = sync_xbox_library(db)
        return result
    except XboxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/disconnect")
def disconnect_xbox(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    update_settings(
        db,
        {
            SETTING_XBOX_REFRESH_TOKEN: "",
            SETTING_XBOX_XUID: "",
            SETTING_XBOX_GAMERTAG: "",
            SETTING_XBOX_GAMERSCORE: "0",
            SETTING_XBOX_LAST_SYNC: "",
            SETTING_XBOX_DEVICE_CODE: "",
            SETTING_XBOX_DEVICE_EXPIRES: "",
        },
    )
    return {"ok": True}
