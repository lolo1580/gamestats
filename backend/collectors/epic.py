from __future__ import annotations

import base64
import logging
import time
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Game, utcnow
from settings_service import (
    SETTING_EPIC_ACCOUNT_ID,
    SETTING_EPIC_DISPLAY_NAME,
    SETTING_EPIC_LAST_SYNC,
    SETTING_EPIC_REFRESH_TOKEN,
    get_integration_settings,
    update_settings,
)
from utils import normalize_name

logger = logging.getLogger(__name__)

EPIC_CLIENT_ID = "34a02cf8f4414e29b15921876da36f9a"
EPIC_CLIENT_SECRET = "daafbccc737745039dffe53d94fc76cf"
EPIC_OAUTH_URL = (
    "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token"
)
EPIC_LIBRARY_URL = (
    "https://library-service.live.use1a.on.epicgames.com/library/api/public/items"
)
EPIC_CATALOG_URL = (
    "https://catalog-public-service-prod06.ol.epicgames.com"
    "/catalog/api/shared/namespace"
)
EPIC_GRAPHQL_URL = "https://launcher.store.epicgames.com/graphql"
EPIC_USER_AGENT = "EpicGamesLauncher/14.0.8-22004686+++Portal+Release-Live"


def redirect_uri() -> str:
    return (
        "https://www.epicgames.com/id/api/redirect"
        f"?clientId={EPIC_CLIENT_ID}&responseType=code"
    )


def auth_url() -> str:
    return (
        "https://www.epicgames.com/id/login?redirectUrl="
        + quote(redirect_uri(), safe="")
    )


def _basic_auth() -> str:
    credentials = f"{EPIC_CLIENT_ID}:{EPIC_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(credentials).decode()


class EpicError(RuntimeError):
    pass


class EpicClient:
    def __init__(self, refresh_token: str = "") -> None:
        self.refresh_token = refresh_token
        self.account_id = ""
        self._client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": EPIC_USER_AGENT,
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EpicClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _token_request(self, data: dict[str, str]) -> dict:
        try:
            response = self._client.post(
                EPIC_OAUTH_URL,
                data=data,
                headers={"Authorization": _basic_auth()},
            )
        except httpx.HTTPError as exc:
            raise EpicError(f"Epic Games injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise EpicError(
                f"Authentification Epic Games refusée ({response.status_code}) : "
                f"{detail}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise EpicError("Réponse Epic Games illisible.") from exc
        if not payload.get("access_token"):
            raise EpicError("Réponse Epic Games incomplète.")
        return payload

    def exchange_code(self, code: str) -> dict:
        errors: list[str] = []
        for grant in ("authorization_code", "exchange_code"):
            key = "code" if grant == "authorization_code" else "exchange_code"
            try:
                return self._token_request(
                    {
                        "grant_type": grant,
                        key: code,
                        "token_type": "eg1",
                    }
                )
            except EpicError as exc:
                errors.append(str(exc))
        raise EpicError(errors[-1] if errors else "Code Epic Games invalide.")

    def refresh(self) -> dict:
        return self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "token_type": "eg1",
            }
        )

    def _get(
        self,
        url: str,
        access_token: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"Authorization": f"bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise EpicError(f"Epic Games injoignable : {exc}") from exc
        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise EpicError(
                f"API Epic Games {response.status_code} : {detail}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise EpicError("Réponse Epic Games illisible.") from exc

    def library_items(self, access_token: str) -> list[dict]:
        records: list[dict] = []
        cursor: str | None = None
        for _ in range(100):
            params = {"includeMetadata": "true"}
            if cursor:
                params["cursor"] = cursor
            data = self._get(EPIC_LIBRARY_URL, access_token, params)
            batch = data.get("records") or []
            if not isinstance(batch, list):
                break
            records.extend(item for item in batch if isinstance(item, dict))
            cursor = (data.get("responseMetadata") or {}).get("nextCursor")
            if not cursor:
                break
        return records

    def catalog_item(
        self, namespace: str, catalog_item_id: str, access_token: str
    ) -> dict | None:
        try:
            data = self._get(
                f"{EPIC_CATALOG_URL}/{quote(namespace, safe='')}/bulk/items",
                access_token,
                {
                    "id": catalog_item_id,
                    "includeDLCDetails": "false",
                    "includeMainGameDetails": "false",
                    "country": "US",
                    "locale": "en-US",
                },
            )
        except EpicError:
            return None
        if not isinstance(data, dict):
            return None
        item = data.get(catalog_item_id)
        return item if isinstance(item, dict) else None

    def _graphql(
        self, access_token: str, query: str, variables: dict
    ) -> dict | None:
        try:
            response = self._client.post(
                EPIC_GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        result = data.get("data") if isinstance(data, dict) else None
        return result if isinstance(result, dict) else None

    def achievements(self, namespace: str, access_token: str) -> tuple[int, int]:
        total = 0
        unlocked = 0
        product_data = self._graphql(
            access_token,
            _PRODUCT_ACHIEVEMENTS_QUERY,
            {"sandboxId": namespace, "locale": "en-US"},
        )
        if product_data:
            product = (product_data.get("Achievement") or {}).get(
                "productAchievementsRecordBySandbox"
            )
            if isinstance(product, dict):
                try:
                    total = int(product.get("totalAchievements") or 0)
                except (TypeError, ValueError):
                    total = 0

        player_data = self._graphql(
            access_token,
            _PLAYER_ACHIEVEMENTS_QUERY,
            {"epicAccountId": self.account_id, "sandboxId": namespace},
        )
        if player_data:
            player = (player_data.get("PlayerAchievement") or {}).get(
                "playerAchievementGameRecordsBySandbox"
            )
            if isinstance(player, dict):
                records = player.get("records") or []
                values: list[int] = []
                if isinstance(records, list):
                    for record in records:
                        if not isinstance(record, dict):
                            continue
                        try:
                            values.append(int(record.get("totalUnlocked") or 0))
                        except (TypeError, ValueError):
                            continue
                unlocked = max(values) if values else 0
        if total and unlocked > total:
            unlocked = total
        return total, unlocked


_PRODUCT_ACHIEVEMENTS_QUERY = """
query Achievement($sandboxId: String!, $locale: String!) {
  Achievement {
    productAchievementsRecordBySandbox(sandboxId: $sandboxId, locale: $locale) {
      sandboxId
      totalAchievements
    }
  }
}
"""

_PLAYER_ACHIEVEMENTS_QUERY = """
query PlayerAchievement($epicAccountId: String!, $sandboxId: String!) {
  PlayerAchievement {
    playerAchievementGameRecordsBySandbox(
      epicAccountId: $epicAccountId
      sandboxId: $sandboxId
    ) {
      records {
        totalUnlocked
      }
    }
  }
}
"""


def _cover(info: dict | None) -> str | None:
    if not isinstance(info, dict):
        return None
    images = info.get("keyImages") or []
    if not isinstance(images, list):
        return None
    by_type: dict[str, str] = {}
    for image in images:
        if not isinstance(image, dict):
            continue
        image_type = image.get("type")
        url = image.get("url")
        if isinstance(image_type, str) and isinstance(url, str) and url:
            by_type[image_type] = url
    for key in (
        "DieselStoreFrontTall",
        "OfferImageTall",
        "CodeRedemption_340x440",
        "Thumbnail",
        "DieselStoreFrontWide",
        "OfferImageWide",
        "featuredMedia",
    ):
        if key in by_type:
            return by_type[key]
    return None


def _title(info: dict | None, record: dict) -> str:
    if isinstance(info, dict):
        value = info.get("title")
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("sandboxName", "appName"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def sync_epic_library(db: Session) -> dict:
    integration = get_integration_settings(db)
    if not integration.epic_refresh_token:
        return {"skipped": True, "reason": "Compte Epic Games non connecté."}

    now = utcnow()
    with EpicClient(integration.epic_refresh_token) as client:
        tokens = client.refresh()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token") or integration.epic_refresh_token
        account_id = str(tokens.get("account_id") or integration.epic_account_id)
        display_name = str(
            tokens.get("displayName") or integration.epic_display_name
        )
        if not access_token or not account_id:
            raise EpicError("Réponse Epic Games incomplète.")
        client.account_id = account_id

        records = client.library_items(access_token)

        games: list[Game] = []
        for record in records:
            if record.get("recordType") != "APPLICATION":
                continue
            if record.get("sandboxType") == "PRIVATE":
                continue
            namespace = str(record.get("namespace") or "").strip()
            catalog_item_id = str(record.get("catalogItemId") or "").strip()
            app_name = str(record.get("appName") or "").strip()
            if (
                not namespace
                or namespace == "ue"
                or not catalog_item_id
                or not app_name
            ):
                continue

            game = db.scalar(
                select(Game).where(Game.epic_catalog_item_id == catalog_item_id)
            )
            info: dict | None = None
            if game is None:
                info = client.catalog_item(namespace, catalog_item_id, access_token)
                title = _title(info, record)
                if not title:
                    continue
                game = db.scalar(
                    select(Game).where(Game.name_key == normalize_name(title))
                )
                if game is None:
                    game = Game(
                        name=title,
                        name_key=normalize_name(title),
                        epic_catalog_item_id=catalog_item_id,
                    )
                    db.add(game)
                time.sleep(0.05)

            if game.epic_catalog_item_id is None:
                conflict = db.scalar(
                    select(Game).where(Game.epic_catalog_item_id == catalog_item_id)
                )
                if conflict is None:
                    game.epic_catalog_item_id = catalog_item_id
            if not game.epic_namespace:
                game.epic_namespace = namespace
            if not game.cover_url:
                if info is None:
                    info = client.catalog_item(
                        namespace, catalog_item_id, access_token
                    )
                cover = _cover(info)
                if cover:
                    game.cover_url = cover
            games.append(game)

        db.commit()

        stale_cutoff = now - timedelta(hours=24)
        candidates = db.scalars(
            select(Game)
            .where(
                Game.epic_namespace.is_not(None),
                or_(
                    Game.epic_achievements_checked_at.is_(None),
                    Game.epic_achievements_checked_at < stale_cutoff,
                ),
            )
            .order_by(Game.updated_at.desc())
            .limit(20)
        ).all()
        for game in candidates:
            total, unlocked = client.achievements(
                str(game.epic_namespace), access_token
            )
            game.epic_achievements_total = max(0, total)
            game.epic_achievements_unlocked = max(0, unlocked)
            game.epic_achievements_checked_at = now
            time.sleep(0.12)
        db.commit()

    update_settings(
        db,
        {
            SETTING_EPIC_REFRESH_TOKEN: refresh_token,
            SETTING_EPIC_ACCOUNT_ID: account_id,
            SETTING_EPIC_DISPLAY_NAME: display_name,
            SETTING_EPIC_LAST_SYNC: now.isoformat(),
        },
    )
    logger.info("Epic Games : %s jeu(x) synchronisé(s).", len(games))
    return {
        "connected": True,
        "name": display_name,
        "games_synced": len(games),
        "last_sync_at": now.isoformat(),
    }
