from __future__ import annotations

import json
import logging
import re
import time
from difflib import SequenceMatcher

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from config import get_settings
from models import Game, utcnow
from settings_service import get_integration_settings
from utils import normalize_name

logger = logging.getLogger(__name__)

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"
_COVER_SIZE_RE = re.compile(r"/t_[^/]+/")


class IGDBError(RuntimeError):
    pass


class IGDBCollector:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._client = httpx.Client(
            timeout=25,
            headers={"User-Agent": "GameStats/1.0 (+self-hosted)"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "IGDBCollector":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _get_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_expires_at - 60:
            return self._token

        try:
            response = self._client.post(
                TWITCH_TOKEN_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
        except httpx.HTTPError as exc:
            raise IGDBError(f"Twitch/IGDB injoignable : {exc}") from exc

        if response.status_code != 200:
            raise IGDBError(f"OAuth Twitch {response.status_code} : {response.text[:200]}")

        data = response.json()
        if not data.get("access_token"):
            raise IGDBError("Réponse OAuth Twitch invalide (access_token absent).")
        self._token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _post(self, body: str, retry: bool = True) -> list[dict]:
        token = self._get_token()
        try:
            response = self._client.post(
                IGDB_GAMES_URL,
                content=body,
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise IGDBError(f"IGDB injoignable : {exc}") from exc

        if response.status_code == 401 and retry:
            self._get_token(force=True)
            return self._post(body, retry=False)

        if response.status_code == 429:
            raise IGDBError("Quota IGDB atteint (429).")
        if response.status_code != 200:
            raise IGDBError(f"IGDB {response.status_code} : {response.text[:200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise IGDBError("Réponse IGDB illisible.") from exc
        return data if isinstance(data, list) else []

    def search(self, name: str) -> list[dict]:
        safe_name = (
            name.replace("\\", " ").replace('"', " ").replace(";", " ").strip()
        )
        body = (
            f'search "{safe_name}"; '
            "fields name,cover.url,genres.name; "
            "limit 5;"
        )
        return self._post(body)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio()


def _cover_url(raw: str | None) -> str | None:
    if not raw:
        return None
    url = f"https:{raw}" if raw.startswith("//") else raw
    if "images.igdb.com" in url:
        url = _COVER_SIZE_RE.sub("/t_cover_big_2x/", url)
    return url


def enrich_games(db: Session, limit: int | None = None) -> dict:
    config = get_settings()
    integration = get_integration_settings(db)
    if not integration.igdb_configured:
        return {"skipped": True, "reason": "IGDB_CLIENT_ID / IGDB_CLIENT_SECRET non configurés."}

    max_games = config.igdb_enrich_limit if limit is None else limit
    if max_games <= 0:
        return {"skipped": False, "enriched": 0}

    games = db.scalars(
        select(Game)
        .where(
            Game.igdb_checked_at.is_(None),
            or_(Game.cover_url.is_(None), Game.genres.is_(None)),
        )
        .order_by(Game.steam_playtime_minutes.desc(), Game.id.asc())
        .limit(max_games)
    ).all()

    enriched = 0
    with IGDBCollector(integration.igdb_client_id, integration.igdb_client_secret) as collector:
        for index, game in enumerate(games):
            if index:
                time.sleep(0.3)  # Respecte la limite IGDB (~4 req/s).

            try:
                results = collector.search(game.name)
            except IGDBError as exc:
                logger.warning("Enrichissement IGDB interrompu : %s", exc)
                db.rollback()
                break

            game.igdb_checked_at = utcnow()
            if not results:
                db.commit()
                continue

            best = max(results, key=lambda item: _similarity(game.name, item.get("name", "")))
            score = _similarity(game.name, best.get("name", ""))
            if score < 0.45:
                logger.debug(
                    "IGDB : pas de correspondance fiable pour '%s' (meilleur : '%s').",
                    game.name,
                    best.get("name"),
                )
                db.commit()
                continue

            game.igdb_id = best.get("id")
            cover = _cover_url((best.get("cover") or {}).get("url"))
            if cover:
                game.cover_url = cover
            genres = [
                genre["name"]
                for genre in best.get("genres") or []
                if isinstance(genre, dict) and genre.get("name")
            ]
            if genres:
                game.genres = json.dumps(genres, ensure_ascii=False)
            enriched += 1
            db.commit()

    logger.info("IGDB : %s jeu(x) enrichi(s).", enriched)
    return {"skipped": False, "enriched": enriched}
