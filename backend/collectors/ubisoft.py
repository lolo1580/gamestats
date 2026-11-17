from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Game, utcnow
from settings_service import (
    SETTING_UBISOFT_LAST_SYNC,
    SETTING_UBISOFT_NAME,
    SETTING_UBISOFT_PROFILE_ID,
    SETTING_UBISOFT_REMEMBER_ME_TICKET,
    SETTING_UBISOFT_USER_ID,
    get_integration_settings,
    update_settings,
)
from utils import ensure_utc, normalize_name

logger = logging.getLogger(__name__)

UBI_BASE = "https://public-ubiservices.ubi.com"
UBI_APP_ID = "4391c956-8943-48eb-8859-07b0778f47b9"


class UbisoftError(RuntimeError):
    pass


class UbisoftClient:
    def __init__(self, remember_me_ticket: str) -> None:
        self.remember_me_ticket = remember_me_ticket
        self._client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "GameStats/1.0 (+self-hosted)",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "UbisoftClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _headers(self, session: dict | None = None) -> dict[str, str]:
        headers = {
            "Ubi-AppId": UBI_APP_ID,
            "Content-Type": "application/json",
            "Ubi-RequestedPlatformType": "uplay",
        }
        if session:
            headers["Authorization"] = f"ubi_v1 t={session['ticket']}"
            if session.get("sessionId"):
                headers["Ubi-SessionId"] = session["sessionId"]
        else:
            headers["Authorization"] = f"ubi_v1 t={self.remember_me_ticket}"
        return headers

    def login(self) -> dict:
        try:
            response = self._client.post(
                f"{UBI_BASE}/v3/profiles/sessions",
                headers=self._headers(),
                json={"rememberMe": True},
            )
        except httpx.HTTPError as exc:
            raise UbisoftError(f"Ubisoft injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise UbisoftError(
                f"Connexion Ubisoft refusée ({response.status_code}) : {detail}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise UbisoftError("Réponse Ubisoft illisible.") from exc
        if not data.get("ticket") or not data.get("profileId"):
            raise UbisoftError(
                "Ticket Ubisoft invalide ou connexion 2FA incomplète."
            )
        return data

    def games_played(self, session: dict) -> list[dict]:
        profile_id = session["profileId"]
        try:
            response = self._client.get(
                f"{UBI_BASE}/v1/profiles/gamesplayed",
                params={"profileIds": profile_id, "limit": "1000"},
                headers=self._headers(session),
            )
            if response.status_code == 404:
                response = self._client.get(
                    f"{UBI_BASE}/v1/profiles/me/gamesplayed",
                    headers=self._headers(session),
                )
        except httpx.HTTPError as exc:
            raise UbisoftError(f"Bibliothèque Ubisoft injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise UbisoftError(
                f"Bibliothèque Ubisoft indisponible ({response.status_code}) : {detail}"
            )
        try:
            return parse_games_played(response.json())
        except ValueError as exc:
            raise UbisoftError("Réponse Ubisoft illisible.") from exc

    def space_name(self, space_id: str, session: dict) -> str | None:
        try:
            response = self._client.get(
                f"{UBI_BASE}/v1/spaces/{space_id}",
                headers=self._headers(session),
            )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        return parse_space_name(data)


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, dict):
        value = value.get("date") or value.get("createdAt") or value.get("updatedAt")
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ensure_utc(parsed)


def parse_games_played(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("gamesPlayed") or payload.get("games") or []
    else:
        entries = []
    if not isinstance(entries, list):
        return []

    result: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        space_id = str(entry.get("spaceId") or "").strip()
        if not space_id:
            continue
        applications = entry.get("applications") or []
        sessions_count = entry.get("sessionsCount")
        if sessions_count is None and isinstance(applications, list):
            counts = [
                app.get("sessionsCount")
                for app in applications
                if isinstance(app, dict) and app.get("sessionsCount") is not None
            ]
            sessions_count = max(counts) if counts else 0
        try:
            sessions_count = int(sessions_count or 0)
        except (TypeError, ValueError):
            sessions_count = 0

        application_ids = [
            str(app.get("applicationId"))
            for app in applications
            if isinstance(app, dict) and app.get("applicationId")
        ]
        result.append(
            {
                "space_id": space_id,
                "sessions_count": sessions_count,
                "first_played_at": _parse_date(entry.get("firstPlayed")),
                "last_played_at": _parse_date(entry.get("lastPlayed")),
                "application_ids": application_ids,
            }
        )
    result.sort(
        key=lambda item: item["last_played_at"] or datetime.min.replace(tzinfo=ensure_utc(utcnow()).tzinfo),
        reverse=True,
    )
    return result


def parse_space_name(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("name", "spaceName", "displayName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = payload.get("space")
    if isinstance(nested, dict):
        for key in ("name", "spaceName", "displayName"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def sync_ubisoft_library(db: Session) -> dict:
    integration = get_integration_settings(db)
    if not integration.ubisoft_remember_me_ticket:
        return {"skipped": True, "reason": "Compte Ubisoft non connecté."}

    now = utcnow()
    with UbisoftClient(integration.ubisoft_remember_me_ticket) as client:
        session = client.login()
        entries = client.games_played(session)

        names: dict[str, str] = {}
        for entry in entries[:100]:
            space_id = entry["space_id"]
            if space_id in names:
                continue
            name = client.space_name(space_id, session)
            if name:
                names[space_id] = name
            time.sleep(0.12)

        for entry in entries:
            space_id = entry["space_id"]
            name = names.get(space_id) or f"Ubisoft {space_id[:8]}"
            game = db.scalar(select(Game).where(Game.ubisoft_space_id == space_id))
            if game is None:
                game = db.scalar(
                    select(Game).where(Game.name_key == normalize_name(name))
                )
            if game is None:
                game = Game(
                    name=name,
                    name_key=normalize_name(name),
                    ubisoft_space_id=space_id,
                )
                db.add(game)
            elif game.ubisoft_space_id is None:
                conflict = db.scalar(
                    select(Game).where(Game.ubisoft_space_id == space_id)
                )
                if conflict is None:
                    game.ubisoft_space_id = space_id

            game.ubisoft_sessions_count = entry["sessions_count"]
            game.ubisoft_first_played_at = entry["first_played_at"]
            game.ubisoft_last_played_at = entry["last_played_at"]

        db.commit()

    update_settings(
        db,
        {
            SETTING_UBISOFT_REMEMBER_ME_TICKET: session.get(
                "rememberMeTicket"
            )
            or integration.ubisoft_remember_me_ticket,
            SETTING_UBISOFT_PROFILE_ID: session["profileId"],
            SETTING_UBISOFT_USER_ID: session.get("userId") or "",
            SETTING_UBISOFT_NAME: session.get("nameOnPlatform") or "",
            SETTING_UBISOFT_LAST_SYNC: now.isoformat(),
        },
    )

    logger.info("Ubisoft : %s jeu(x) synchronisé(s).", len(entries))
    return {
        "connected": True,
        "name": session.get("nameOnPlatform"),
        "games_synced": len(entries),
        "last_sync_at": now.isoformat(),
    }
