from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Game, utcnow
from settings_service import (
    SETTING_XBOX_CLIENT_ID,
    SETTING_XBOX_GAMERSCORE,
    SETTING_XBOX_GAMERTAG,
    SETTING_XBOX_LAST_SYNC,
    SETTING_XBOX_REFRESH_TOKEN,
    SETTING_XBOX_XUID,
    get_integration_settings,
    update_settings,
)
from utils import ensure_utc, normalize_name

logger = logging.getLogger(__name__)

DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBOX_SCOPE = "XboxLive.signin XboxLive.offline_access"
USER_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
PROFILE_URL = "https://profile.xboxlive.com/users/me/profile/settings"
TITLEHUB_URL = (
    "https://titlehub.xboxlive.com/users/xuid({xuid})"
    "/titles/titleHistory/decoration/achievement,image"
)

XSTS_ERRORS = {
    2148916233: "Ce compte Microsoft n'a pas de profil Xbox.",
    2148916235: "Xbox Live n'est pas disponible dans ce pays.",
    2148916238: "Un compte enfant doit être ajouté à une famille Microsoft.",
}


class XboxError(RuntimeError):
    pass


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=30,
        headers={
            "User-Agent": "GameStats/1.0 (+self-hosted)",
            "Accept": "application/json",
        },
    )


def _response_error(response: httpx.Response, prefix: str) -> XboxError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    description = (
        payload.get("error_description")
        or payload.get("error")
        or " ".join(response.text.split())[:300]
    )
    return XboxError(f"{prefix} ({response.status_code}) : {description}")


def start_device_code(client_id: str) -> dict:
    try:
        with _http_client() as client:
            response = client.post(
                DEVICE_CODE_URL,
                data={"client_id": client_id, "scope": XBOX_SCOPE},
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Microsoft injoignable : {exc}") from exc
    if response.status_code != 200:
        raise _response_error(response, "Impossible de démarrer la connexion Microsoft")
    return response.json()


def poll_device_code(client_id: str, device_code: str) -> dict:
    try:
        with _http_client() as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": client_id,
                    "device_code": device_code,
                },
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Microsoft injoignable : {exc}") from exc

    if response.status_code == 200:
        return {"status": "connected", "tokens": response.json()}

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error")
    if error in {"authorization_pending", "slow_down"}:
        return {"status": "pending"}
    if error in {"expired_token", "bad_verification_code", "code_expired"}:
        return {"status": "expired"}
    if error in {"authorization_declined", "access_denied"}:
        return {"status": "error", "message": "Connexion refusée."}
    return {
        "status": "error",
        "message": payload.get("error_description")
        or payload.get("error")
        or f"Réponse Microsoft {response.status_code}.",
    }


def refresh_microsoft_token(client_id: str, refresh_token: str) -> dict:
    try:
        with _http_client() as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                    "scope": XBOX_SCOPE,
                },
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Microsoft injoignable : {exc}") from exc
    if response.status_code != 200:
        raise _response_error(response, "Rafraîchissement du token Microsoft impossible")
    return response.json()


def authenticate_xbox(access_token: str) -> dict:
    user_body = {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={access_token}",
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    }
    try:
        with _http_client() as client:
            user_response = client.post(
                USER_AUTH_URL,
                json=user_body,
                headers={"x-xbl-contract-version": "1"},
            )
            if user_response.status_code != 200:
                raise _response_error(user_response, "Authentification Xbox impossible")
            user_data = user_response.json()
            user_token = user_data.get("Token")
            xui = (user_data.get("DisplayClaims") or {}).get("xui") or []
            if not user_token or not xui:
                raise XboxError("Réponse d'authentification Xbox incomplète.")

            xsts_response = client.post(
                XSTS_URL,
                json={
                    "Properties": {
                        "UserTokens": [user_token],
                        "SandboxId": "RETAIL",
                    },
                    "RelyingParty": "http://xboxlive.com",
                    "TokenType": "JWT",
                },
                headers={"x-xbl-contract-version": "1"},
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Xbox Live injoignable : {exc}") from exc

    if xsts_response.status_code == 401:
        try:
            payload = xsts_response.json()
        except ValueError:
            payload = {}
        xerr = payload.get("XErr")
        raise XboxError(XSTS_ERRORS.get(xerr, f"XSTS a refusé la connexion (XErr {xerr})."))
    if xsts_response.status_code != 200:
        raise _response_error(xsts_response, "Autorisation XSTS impossible")

    xsts_data = xsts_response.json()
    xsts_token = xsts_data.get("Token")
    xsts_xui = (xsts_data.get("DisplayClaims") or {}).get("xui") or []
    if not xsts_token or not xsts_xui:
        raise XboxError("Réponse XSTS incomplète.")
    return {
        "xuid": str(xsts_xui[0].get("xid") or ""),
        "userhash": str(xsts_xui[0].get("uhs") or ""),
        "token": xsts_token,
    }


def _auth_header(auth: dict) -> dict[str, str]:
    return {
        "Authorization": f"XBL3.0 x={auth['userhash']};{auth['token']}",
        "x-xbl-contract-version": "3",
        "Accept-Language": "en-US",
    }


def parse_profile(payload: dict) -> dict:
    users = payload.get("profileUsers") or []
    if not users:
        raise XboxError("Profil Xbox introuvable.")
    settings = {
        item.get("id"): item.get("value")
        for item in users[0].get("settings") or []
        if item.get("id")
    }
    try:
        gamerscore = int(settings.get("Gamerscore") or 0)
    except (TypeError, ValueError):
        gamerscore = 0
    return {
        "gamertag": str(settings.get("Gamertag") or ""),
        "gamerscore": gamerscore,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ensure_utc(parsed)


def parse_titles(payload: dict) -> list[dict]:
    titles: list[dict] = []
    for item in payload.get("titles") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {None, "Game"}:
            continue
        title_id = str(item.get("titleId") or "").strip()
        name = str(item.get("name") or "").strip()
        if not title_id or not name:
            continue
        achievement = item.get("achievement") or {}
        history = item.get("titleHistory") or {}
        try:
            achievements_total = int(achievement.get("totalAchievements") or 0)
            achievements_unlocked = int(achievement.get("currentAchievements") or 0)
            gamerscore = int(achievement.get("currentGamerscore") or 0)
            gamerscore_total = int(achievement.get("totalGamerscore") or 0)
        except (TypeError, ValueError):
            achievements_total = achievements_unlocked = 0
            gamerscore = gamerscore_total = 0
        titles.append(
            {
                "title_id": title_id,
                "name": name,
                "achievements_total": achievements_total,
                "achievements_unlocked": achievements_unlocked,
                "gamerscore": gamerscore,
                "gamerscore_total": gamerscore_total,
                "last_played_at": _parse_datetime(history.get("lastTimePlayed")),
                "cover_url": item.get("displayImage") or None,
            }
        )
    return titles


def fetch_profile(auth: dict) -> dict:
    try:
        with _http_client() as client:
            response = client.get(
                PROFILE_URL,
                params={"settings": "Gamertag,Gamerscore"},
                headers=_auth_header(auth),
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Profil Xbox injoignable : {exc}") from exc
    if response.status_code != 200:
        raise _response_error(response, "Profil Xbox indisponible")
    return parse_profile(response.json())


def fetch_title_history(xuid: str, auth: dict) -> dict:
    headers = _auth_header(auth)
    headers["x-xbl-contract-version"] = "2"
    try:
        with _http_client() as client:
            response = client.get(
                TITLEHUB_URL.format(xuid=xuid),
                params={"maxItems": "200"},
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise XboxError(f"Bibliothèque Xbox injoignable : {exc}") from exc
    if response.status_code != 200:
        raise _response_error(response, "Bibliothèque Xbox indisponible")
    return response.json()


def sync_xbox_library(db: Session) -> dict:
    integration = get_integration_settings(db)
    if not integration.xbox_client_id:
        return {"skipped": True, "reason": "Client ID Xbox non configuré."}
    if not integration.xbox_refresh_token:
        return {"skipped": True, "reason": "Compte Xbox non connecté."}

    tokens = refresh_microsoft_token(
        integration.xbox_client_id, integration.xbox_refresh_token
    )
    access_token = tokens.get("access_token")
    if not access_token:
        raise XboxError("Token Microsoft invalide.")
    refresh_token = tokens.get("refresh_token") or integration.xbox_refresh_token

    auth = authenticate_xbox(access_token)
    xuid = auth["xuid"]
    if not xuid:
        raise XboxError("XUID Xbox introuvable.")

    profile = fetch_profile(auth)
    titles = parse_titles(fetch_title_history(xuid, auth))
    now = utcnow()

    for title in titles:
        game = db.scalar(
            select(Game).where(Game.xbox_title_id == title["title_id"])
        )
        if game is None:
            game = db.scalar(
                select(Game).where(Game.name_key == normalize_name(title["name"]))
            )
        if game is None:
            game = Game(
                name=title["name"],
                name_key=normalize_name(title["name"]),
                xbox_title_id=title["title_id"],
            )
            db.add(game)
        elif game.xbox_title_id is None:
            conflict = db.scalar(
                select(Game).where(Game.xbox_title_id == title["title_id"])
            )
            if conflict is None:
                game.xbox_title_id = title["title_id"]

        if not game.cover_url and title["cover_url"]:
            game.cover_url = title["cover_url"]
        game.xbox_achievements_total = title["achievements_total"]
        game.xbox_achievements_unlocked = title["achievements_unlocked"]
        game.xbox_gamerscore = title["gamerscore"]
        game.xbox_gamerscore_total = title["gamerscore_total"]
        game.xbox_last_played_at = title["last_played_at"]

    db.commit()

    update_settings(
        db,
        {
            SETTING_XBOX_REFRESH_TOKEN: refresh_token,
            SETTING_XBOX_GAMERTAG: profile["gamertag"],
            SETTING_XBOX_XUID: xuid,
            SETTING_XBOX_GAMERSCORE: str(profile["gamerscore"]),
            SETTING_XBOX_LAST_SYNC: now.isoformat(),
        },
    )

    logger.info(
        "Xbox : %s jeu(x) synchronisé(s), gamerscore %s.",
        len(titles),
        profile["gamerscore"],
    )
    return {
        "skipped": False,
        "titles_synced": len(titles),
        "gamerscore": profile["gamerscore"],
        "last_sync_at": now.isoformat(),
        "gamertag": profile["gamertag"],
    }


def device_code_expiry(expires_in: int) -> datetime:
    return utcnow() + timedelta(seconds=max(60, expires_in))
