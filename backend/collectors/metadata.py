from __future__ import annotations

import difflib
import logging
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from config import get_settings
from models import Game, utcnow
from settings_service import (
    SETTING_METADATA_LAST_SYNC,
    get_integration_settings,
    update_settings,
)
from utils import ensure_utc

logger = logging.getLogger(__name__)

MOBYGAMES_API = "https://api.mobygames.com/v1"
OPENCRITIC_API = "https://opencritic-api.p.rapidapi.com"
OPENCRITIC_HOST = "opencritic-api.p.rapidapi.com"
HLTB_BASE = "https://howlongtobeat.com"
USER_AGENT = "GameStats/1.7 (+self-hosted metadata enrichment)"

_EDITION_RE = re.compile(
    r"\b("
    r"game of the year|goty|complete edition|definitive edition|"
    r"ultimate edition|deluxe edition|enhanced edition|legendary edition|"
    r"special edition|collector'?s? edition|standard edition"
    r")\b.*$",
    re.IGNORECASE,
)


class MetadataProviderError(RuntimeError):
    pass


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = _EDITION_RE.sub("", f" {text} ").strip()
    return re.sub(r"\s+", " ", text)


def title_similarity(left: str, right: str) -> float:
    a = normalize_title(left)
    b = normalize_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def best_candidate(
    title: str,
    candidates: list[dict],
    name_key: str,
    *,
    threshold: float = 0.82,
    distance_key: str | None = None,
    max_distance: float | None = None,
) -> dict | None:
    best: dict | None = None
    best_score = 0.0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        name = candidate.get(name_key)
        if not isinstance(name, str) or not name.strip():
            continue
        if distance_key and max_distance is not None:
            distance = candidate.get(distance_key)
            try:
                if distance is not None and float(distance) > max_distance:
                    continue
            except (TypeError, ValueError):
                pass
        score = title_similarity(title, name)
        if score > best_score:
            best = candidate
            best_score = score
    return best if best_score >= threshold else None


def _date_only(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value.strip())
    return match.group(1) if match else None


def _image_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    return f"https:{url}" if url.startswith("//") else url


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_stale(value: datetime | None, cutoff: datetime) -> bool:
    if value is None:
        return True
    normalized = ensure_utc(value)
    return normalized < cutoff


class MobyGamesClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.Client(
            timeout=30,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MobyGamesClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, str]) -> dict:
        wait = 1.05 - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.get(
                f"{MOBYGAMES_API}{path}",
                params={**params, "api_key": self.api_key},
            )
        except httpx.HTTPError as exc:
            raise MetadataProviderError(f"MobyGames injoignable : {exc}") from exc
        self._last_request = time.monotonic()
        if response.status_code in {401, 403}:
            raise MetadataProviderError("Clé API MobyGames invalide ou refusée.")
        if response.status_code == 429:
            raise MetadataProviderError("Quota MobyGames atteint.")
        if response.status_code != 200:
            raise MetadataProviderError(
                f"MobyGames {response.status_code} : "
                f"{' '.join(response.text.split())[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MetadataProviderError("Réponse MobyGames illisible.") from exc
        return payload if isinstance(payload, dict) else {}

    def enrich(self, title: str) -> dict | None:
        payload = self._get(
            "/games", {"title": title, "format": "normal", "limit": "10"}
        )
        games = payload.get("games") or []
        if not isinstance(games, list):
            return None
        match = best_candidate(title, games, "title", threshold=0.82)
        if match is None:
            return None

        release_dates: list[str] = []
        for platform in match.get("platforms") or []:
            if not isinstance(platform, dict):
                continue
            date = _date_only(platform.get("first_release_date"))
            if date:
                release_dates.append(date)
        cover = match.get("sample_cover") or {}
        score = _float(match.get("moby_score"))
        return {
            "id": _int(match.get("game_id")) or None,
            "url": match.get("moby_url"),
            "score": score,
            "num_votes": _int(match.get("num_votes")),
            "release_date": min(release_dates) if release_dates else None,
            "cover_url": _image_url(
                cover.get("image") if isinstance(cover, dict) else None
            ),
        }


class OpenCriticClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.Client(
            timeout=30,
            headers={
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": OPENCRITIC_HOST,
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenCriticClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        wait = 0.55 - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = self._client.get(
                f"{OPENCRITIC_API}{path}", params=params
            )
        except httpx.HTTPError as exc:
            raise MetadataProviderError(
                f"OpenCritic injoignable : {exc}"
            ) from exc
        self._last_request = time.monotonic()
        if response.status_code in {401, 403}:
            raise MetadataProviderError(
                "Clé RapidAPI OpenCritic invalide ou abonnement inactif."
            )
        if response.status_code == 429:
            raise MetadataProviderError("Quota OpenCritic atteint.")
        if response.status_code != 200:
            raise MetadataProviderError(
                f"OpenCritic {response.status_code} : "
                f"{' '.join(response.text.split())[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MetadataProviderError("Réponse OpenCritic illisible.") from exc

    def enrich(self, title: str) -> dict | None:
        results = self._get("/game/search", {"criteria": title})
        if not isinstance(results, list):
            return None
        match = best_candidate(
            title,
            results,
            "name",
            threshold=0.72,
            distance_key="dist",
            max_distance=0.45,
        )
        if match is None:
            return None
        game_id = _int(match.get("id"))
        if not game_id:
            return None
        detail = self._get(f"/game/{game_id}")
        if not isinstance(detail, dict):
            return None
        if detail.get("type") in {"DLC", "EXPANSION", "EPISODE"}:
            return None

        score = _float(detail.get("topCriticScore"))
        if score is not None and score < 0:
            score = None
        recommended: int | None = None
        raw_recommended = detail.get("percentRecommended")
        if raw_recommended is not None:
            try:
                value = int(round(float(raw_recommended)))
            except (TypeError, ValueError):
                value = -1
            if value >= 0:
                recommended = value
        images = detail.get("images") or {}
        cover: str | None = None
        if isinstance(images, dict):
            box = images.get("box") or {}
            masthead = images.get("masthead") or {}
            if isinstance(box, dict):
                cover = _image_url(box.get("og"))
            if not cover and isinstance(masthead, dict):
                cover = _image_url(masthead.get("lg") or masthead.get("sm"))
        return {
            "id": game_id,
            "url": detail.get("url"),
            "score": score,
            "tier": detail.get("tier") or None,
            "reviews": _int(detail.get("numReviews")),
            "recommended": recommended,
            "release_date": _date_only(detail.get("firstReleaseDate")),
            "cover_url": cover,
        }


class HowLongToBeatClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Referer": f"{HLTB_BASE}/",
                "Origin": HLTB_BASE,
            },
        )
        self._token: str | None = None
        self._token_at = 0.0
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HowLongToBeatClient":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _wait(self, seconds: float) -> None:
        wait = seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _refresh_token(self) -> str:
        self._wait(0.8)
        try:
            response = self._client.get(
                f"{HLTB_BASE}/api/search/site/init",
                params={"t": int(time.time() * 1000)},
            )
        except httpx.HTTPError as exc:
            raise MetadataProviderError(
                f"HowLongToBeat injoignable : {exc}"
            ) from exc
        if response.status_code == 429:
            raise MetadataProviderError("Quota HowLongToBeat atteint.")
        if response.status_code != 200:
            raise MetadataProviderError(
                f"HowLongToBeat init {response.status_code}."
            )
        try:
            token = response.json().get("token")
        except ValueError as exc:
            raise MetadataProviderError(
                "Réponse HowLongToBeat illisible."
            ) from exc
        if not isinstance(token, str) or not token:
            raise MetadataProviderError("Token HowLongToBeat absent.")
        self._token = token
        self._token_at = time.monotonic()
        return token

    def _search(self, title: str, retry: bool = True) -> list[dict]:
        token = self._token
        if not token or time.monotonic() - self._token_at > 600:
            token = self._refresh_token()
        payload = {
            "searchType": "games",
            "searchTerms": title.split(),
            "searchPage": 1,
            "size": 20,
            "searchOptions": {
                "games": {
                    "userId": 0,
                    "platform": "",
                    "sortCategory": "popular",
                    "rangeCategory": "main",
                    "rangeTime": {"min": 0, "max": 0},
                    "gameplay": {
                        "perspective": "",
                        "flow": "",
                        "genre": "",
                        "difficulty": "",
                    },
                    "rangeYear": {"max": "", "min": ""},
                    "modifier": "",
                },
                "users": {"sortCategory": "postcount"},
                "lists": {"sortCategory": "follows"},
                "filter": "",
                "sort": 0,
                "randomizer": 0,
            },
            "useCache": True,
        }
        self._wait(1.0)
        try:
            response = self._client.post(
                f"{HLTB_BASE}/api/search/site",
                json=payload,
                headers={"x-auth-token": token},
            )
        except httpx.HTTPError as exc:
            raise MetadataProviderError(
                f"HowLongToBeat injoignable : {exc}"
            ) from exc
        if response.status_code == 403 and retry:
            self._token = None
            self._refresh_token()
            return self._search(title, retry=False)
        if response.status_code == 429:
            raise MetadataProviderError("Quota HowLongToBeat atteint.")
        if response.status_code != 200:
            raise MetadataProviderError(
                f"HowLongToBeat {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MetadataProviderError(
                "Réponse HowLongToBeat illisible."
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        return data if isinstance(data, list) else []

    def enrich(self, title: str) -> dict | None:
        results = [
            item
            for item in self._search(title)
            if isinstance(item, dict) and item.get("game_type") == "game"
        ]
        match = best_candidate(title, results, "game_name", threshold=0.8)
        if match is None:
            return None
        game_id = _int(match.get("game_id"))
        if not game_id:
            return None
        return {
            "id": game_id,
            "url": f"{HLTB_BASE}/game/{game_id}",
            "main_minutes": round(_int(match.get("comp_main")) / 60),
            "main_extra_minutes": round(_int(match.get("comp_plus")) / 60),
            "completionist_minutes": round(_int(match.get("comp_100")) / 60),
        }


def enrich_metadata(db: Session, limit: int | None = None) -> dict:
    integration = get_integration_settings(db)
    providers = []
    if integration.mobygames_api_key:
        providers.append("mobygames")
    if integration.opencritic_api_key:
        providers.append("opencritic")
    if integration.hltb_enabled:
        providers.append("hltb")
    if not providers:
        return {
            "skipped": True,
            "reason": "Aucun fournisseur de métadonnées activé.",
            "last_sync_at": None,
        }

    settings = get_settings()
    now = utcnow()
    cutoff = now - timedelta(days=30)
    max_games = limit or max(1, settings.metadata_enrich_limit)
    conditions = []
    if integration.mobygames_api_key:
        conditions.append(
            or_(
                Game.mobygames_checked_at.is_(None),
                Game.mobygames_checked_at < cutoff,
            )
        )
    if integration.opencritic_api_key:
        conditions.append(
            or_(
                Game.opencritic_checked_at.is_(None),
                Game.opencritic_checked_at < cutoff,
            )
        )
    if integration.hltb_enabled:
        conditions.append(
            or_(
                Game.hltb_checked_at.is_(None),
                Game.hltb_checked_at < cutoff,
            )
        )

    games = db.scalars(
        select(Game)
        .where(or_(*conditions))
        .order_by(Game.updated_at.desc())
        .limit(max_games)
    ).all()

    moby_client = (
        MobyGamesClient(integration.mobygames_api_key)
        if integration.mobygames_api_key
        else None
    )
    oc_client = (
        OpenCriticClient(integration.opencritic_api_key)
        if integration.opencritic_api_key
        else None
    )
    hltb_client = HowLongToBeatClient() if integration.hltb_enabled else None

    matched = {"mobygames": 0, "opencritic": 0, "hltb": 0}
    errors: list[str] = []
    opencritic_calls = 0
    oc_limit = max(0, settings.opencritic_enrich_limit)

    try:
        for game in games:
            if moby_client and _is_stale(game.mobygames_checked_at, cutoff):
                try:
                    data = moby_client.enrich(game.name)
                    if data:
                        game.mobygames_id = data["id"] or game.mobygames_id
                        game.mobygames_url = data["url"] or game.mobygames_url
                        if data["score"] is not None:
                            game.mobygames_score = data["score"]
                        if data["num_votes"]:
                            game.mobygames_num_votes = data["num_votes"]
                        if data["release_date"] and not game.release_date:
                            game.release_date = data["release_date"]
                        if data["cover_url"] and not game.cover_url:
                            game.cover_url = data["cover_url"]
                        matched["mobygames"] += 1
                    game.mobygames_checked_at = now
                except MetadataProviderError as exc:
                    logger.warning("MobyGames ignoré : %s", exc)
                    errors.append(str(exc))
                    moby_client.close()
                    moby_client = None

            if (
                oc_client
                and opencritic_calls < oc_limit
                and _is_stale(game.opencritic_checked_at, cutoff)
            ):
                opencritic_calls += 1
                try:
                    data = oc_client.enrich(game.name)
                    if data:
                        game.opencritic_id = data["id"] or game.opencritic_id
                        game.opencritic_url = data["url"] or game.opencritic_url
                        if data["score"] is not None:
                            game.opencritic_score = data["score"]
                        if data["tier"]:
                            game.opencritic_tier = data["tier"]
                        if data["reviews"]:
                            game.opencritic_reviews = data["reviews"]
                        if data["recommended"] is not None:
                            game.opencritic_recommended = data["recommended"]
                        if data["release_date"] and not game.release_date:
                            game.release_date = data["release_date"]
                        if data["cover_url"] and not game.cover_url:
                            game.cover_url = data["cover_url"]
                        matched["opencritic"] += 1
                    game.opencritic_checked_at = now
                except MetadataProviderError as exc:
                    logger.warning("OpenCritic ignoré : %s", exc)
                    errors.append(str(exc))
                    oc_client.close()
                    oc_client = None

            if hltb_client and _is_stale(game.hltb_checked_at, cutoff):
                try:
                    data = hltb_client.enrich(game.name)
                    if data:
                        game.hltb_id = data["id"] or game.hltb_id
                        game.hltb_url = data["url"] or game.hltb_url
                        game.hltb_main_minutes = data["main_minutes"]
                        game.hltb_main_extra_minutes = data["main_extra_minutes"]
                        game.hltb_completionist_minutes = data[
                            "completionist_minutes"
                        ]
                        matched["hltb"] += 1
                    game.hltb_checked_at = now
                except MetadataProviderError as exc:
                    logger.warning("HowLongToBeat ignoré : %s", exc)
                    errors.append(str(exc))
                    hltb_client.close()
                    hltb_client = None

            db.commit()
    finally:
        for client in (moby_client, oc_client, hltb_client):
            if client is not None:
                client.close()

    update_settings(
        db, {SETTING_METADATA_LAST_SYNC: now.isoformat()}
    )
    return {
        "skipped": False,
        "reason": None,
        "message": " · ".join(dict.fromkeys(errors)) or None,
        "games_processed": len(games),
        "mobygames_matched": matched["mobygames"],
        "opencritic_matched": matched["opencritic"],
        "hltb_matched": matched["hltb"],
        "last_sync_at": now.isoformat(),
    }
