from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Game, utcnow
from settings_service import (
    SETTING_GOG_LAST_SYNC,
    SETTING_GOG_REFRESH_TOKEN,
    SETTING_GOG_USER_ID,
    SETTING_GOG_USERNAME,
    get_integration_settings,
    update_settings,
)
from utils import ensure_utc, normalize_name

logger = logging.getLogger(__name__)

GOG_CLIENT_ID = "46899977096215655"
GOG_CLIENT_SECRET = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
GOG_REDIRECT_URI = "https://embed.gog.com/on_login_success?origin=client"
GOG_AUTH_URL = (
    "https://auth.gog.com/auth?"
    f"client_id={GOG_CLIENT_ID}"
    f"&redirect_uri={quote(GOG_REDIRECT_URI, safe='')}"
    "&response_type=code&layout=client2"
)
GOG_TOKEN_URL = "https://auth.gog.com/token"
GOG_API = "https://embed.gog.com"
GOG_PRODUCT_API = "https://api.gog.com"
GOG_GAMEPLAY_API = "https://gameplay.gog.com"


class GogError(RuntimeError):
    pass


def auth_url() -> str:
    return GOG_AUTH_URL


class GogClient:
    def __init__(self, refresh_token: str = "") -> None:
        self.refresh_token = refresh_token
        self._client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "GameStats/1.0 (+self-hosted)",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GogClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def exchange_code(self, code: str) -> dict:
        return self._token_request(
            {
                "client_id": GOG_CLIENT_ID,
                "client_secret": GOG_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": GOG_REDIRECT_URI,
            },
            "Échange du code GOG impossible",
        )

    def refresh(self) -> dict:
        return self._token_request(
            {
                "client_id": GOG_CLIENT_ID,
                "client_secret": GOG_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            "Rafraîchissement du token GOG impossible",
        )

    def _token_request(self, params: dict[str, str], label: str) -> dict:
        try:
            response = self._client.get(GOG_TOKEN_URL, params=params)
        except httpx.HTTPError as exc:
            raise GogError(f"GOG injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise GogError(f"{label} ({response.status_code}) : {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise GogError("Réponse GOG illisible.") from exc

    def _get(self, url: str, access_token: str, params: dict | None = None) -> Any:
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise GogError(f"GOG injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise GogError(f"GOG API {response.status_code} : {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise GogError("Réponse GOG illisible.") from exc

    def user_data(self, access_token: str) -> dict:
        return self._get(f"{GOG_API}/userData.json", access_token)

    def owned_product_ids(self, access_token: str) -> list[int]:
        data = self._get(f"{GOG_API}/user/data/games", access_token)
        ids: list[int] = []
        for value in data.get("owned") or []:
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return ids

    def products(self, product_ids: list[int]) -> list[dict]:
        products: list[dict] = []
        for offset in range(0, len(product_ids), 50):
            batch = product_ids[offset : offset + 50]
            try:
                response = self._client.get(
                    f"{GOG_PRODUCT_API}/products",
                    params={"ids": ",".join(str(item) for item in batch)},
                )
            except httpx.HTTPError as exc:
                raise GogError(f"API produits GOG injoignable : {exc}") from exc
            if response.status_code != 200:
                raise GogError(
                    f"API produits GOG {response.status_code} : "
                    f"{' '.join(response.text.split())[:200]}"
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise GogError("Réponse GOG produits illisible.") from exc
            if isinstance(data, list):
                products.extend(item for item in data if isinstance(item, dict))
            time.sleep(0.1)
        return products

    def achievements(self, product_id: int, user_id: str, access_token: str) -> tuple[int, int]:
        try:
            response = self._client.get(
                f"{GOG_GAMEPLAY_API}/clients/{product_id}/users/{user_id}/achievements",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError:
            return 0, 0
        if response.status_code in {204, 404}:
            return 0, 0
        if response.status_code != 200:
            return 0, 0
        try:
            data = response.json()
        except ValueError:
            return 0, 0
        items = data.get("items") or []
        unlocked = sum(1 for item in items if isinstance(item, dict) and item.get("date_unlocked"))
        try:
            total = int(data.get("total_count") or len(items))
        except (TypeError, ValueError):
            total = len(items)
        return total, unlocked


def _cover(product: dict) -> str | None:
    images = product.get("images") or {}
    for key in ("background", "logo2x", "logo", "icon"):
        value = images.get(key)
        if isinstance(value, str) and value:
            return f"https:{value}" if value.startswith("//") else value
    return None


def sync_gog_library(db: Session) -> dict:
    integration = get_integration_settings(db)
    if not integration.gog_refresh_token:
        return {"skipped": True, "reason": "Compte GOG non connecté."}

    now = utcnow()
    with GogClient(integration.gog_refresh_token) as client:
        tokens = client.refresh()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token") or integration.gog_refresh_token
        user_id = str(tokens.get("user_id") or integration.gog_user_id)
        if not access_token or not user_id:
            raise GogError("Token GOG incomplet.")

        user = client.user_data(access_token)
        username = str(user.get("username") or integration.gog_username)
        product_ids = client.owned_product_ids(access_token)
        products = client.products(product_ids)

        games: list[Game] = []
        for product in products:
            game_type = product.get("game_type")
            if game_type and game_type != "game":
                continue
            try:
                product_id = int(product.get("id"))
            except (TypeError, ValueError):
                continue
            title = str(product.get("title") or f"GOG {product_id}").strip()
            game = db.scalar(select(Game).where(Game.gog_product_id == product_id))
            if game is None:
                game = db.scalar(
                    select(Game).where(Game.name_key == normalize_name(title))
                )
            if game is None:
                game = Game(
                    name=title,
                    name_key=normalize_name(title),
                    gog_product_id=product_id,
                )
                db.add(game)
            elif game.gog_product_id is None:
                conflict = db.scalar(
                    select(Game).where(Game.gog_product_id == product_id)
                )
                if conflict is None:
                    game.gog_product_id = product_id
            if not game.cover_url:
                game.cover_url = _cover(product)
            games.append(game)

        db.commit()

        stale_cutoff = now - timedelta(hours=24)
        candidates = db.scalars(
            select(Game)
            .where(
                Game.gog_product_id.is_not(None),
                or_(
                    Game.gog_achievements_checked_at.is_(None),
                    Game.gog_achievements_checked_at < stale_cutoff,
                ),
            )
            .order_by(Game.updated_at.desc())
            .limit(20)
        ).all()
        for game in candidates:
            total, unlocked = client.achievements(
                int(game.gog_product_id), user_id, access_token
            )
            game.gog_achievements_total = total
            game.gog_achievements_unlocked = unlocked
            game.gog_achievements_checked_at = now
            time.sleep(0.12)
        db.commit()

    update_settings(
        db,
        {
            SETTING_GOG_REFRESH_TOKEN: refresh_token,
            SETTING_GOG_USER_ID: user_id,
            SETTING_GOG_USERNAME: username,
            SETTING_GOG_LAST_SYNC: now.isoformat(),
        },
    )
    logger.info("GOG : %s jeu(x) synchronisé(s).", len(games))
    return {
        "connected": True,
        "name": username,
        "games_synced": len(games),
        "last_sync_at": now.isoformat(),
    }


def gog_profile(refresh_token: str) -> dict:
    with GogClient(refresh_token) as client:
        tokens = client.refresh()
        access = tokens.get("access_token")
        if not access:
            raise GogError("Token GOG invalide.")
        user = client.user_data(access)
        return {
            "refresh_token": tokens.get("refresh_token") or refresh_token,
            "user_id": str(tokens.get("user_id") or ""),
            "username": str(user.get("username") or ""),
        }
