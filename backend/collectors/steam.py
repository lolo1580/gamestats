from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from config import get_settings
from models import Game, GameSession, PlaytimeSnapshot, utcnow
from utils import ensure_utc, normalize_name

logger = logging.getLogger(__name__)

STEAM_API = "https://api.steampowered.com"


class SteamError(RuntimeError):
    pass


class SteamCollector:
    def __init__(self, api_key: str, steam_id: str) -> None:
        self.api_key = api_key
        self.steam_id = steam_id
        self._client = httpx.Client(
            timeout=25,
            headers={"User-Agent": "GameStats/1.0 (+self-hosted)"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SteamCollector":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    def _get(self, path: str, params: dict) -> dict:
        query = {**params, "key": self.api_key, "format": "json"}
        try:
            response = self._client.get(f"{STEAM_API}{path}", params=query)
        except httpx.HTTPError as exc:
            raise SteamError(f"Steam injoignable : {exc}") from exc

        if response.status_code != 200:
            detail = " ".join(response.text.split())[:300]
            raise SteamError(f"Steam API {response.status_code} : {detail}")

        try:
            return response.json()
        except ValueError as exc:
            raise SteamError("Réponse Steam illisible (JSON invalide).") from exc

    def owned_games(self) -> list[dict]:
        data = self._get(
            "/IPlayerService/GetOwnedGames/v0001/",
            {
                "steamid": self.steam_id,
                "include_appinfo": 1,
                "include_played_free_games": 1,
            },
        )
        response = data.get("response")
        if response is None:
            raise SteamError(
                "Réponse Steam vide : vérifiez que le profil et les détails de jeu sont publics."
            )
        return response.get("games", []) or []

    def achievements(self, app_id: int) -> tuple[int, int] | None:
        data = self._get(
            "/ISteamUserStats/GetPlayerAchievements/v0001/",
            {"steamid": self.steam_id, "appid": app_id, "l": "french"},
        )
        stats = data.get("playerstats") or {}
        achievements = stats.get("achievements")
        if not stats.get("success") or not isinstance(achievements, list):
            return None
        total = len(achievements)
        unlocked = sum(1 for item in achievements if item.get("achieved") == 1)
        return total, unlocked


def _timestamp(value: int) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _achievement_key(game: Game) -> float:
    played_at = ensure_utc(game.last_steam_play_at)
    return played_at.timestamp() if played_at else 0.0


def sync_steam_library(db: Session) -> dict:
    settings = get_settings()
    if not settings.steam_configured:
        return {"skipped": True, "reason": "STEAM_API_KEY / STEAM_ID non configurés."}

    now = utcnow()
    created = 0
    updated = 0
    sessions_created = 0
    achievement_candidates: list[Game] = []

    with SteamCollector(settings.steam_api_key, settings.steam_id) as collector:
        owned_games = collector.owned_games()
        logger.info("Steam : %s jeu(x) dans la bibliothèque.", len(owned_games))

        for entry in owned_games:
            app_id = int(entry.get("appid") or 0)
            if not app_id:
                continue
            name = str(entry.get("name") or f"App Steam {app_id}").strip()
            total = int(entry.get("playtime_forever") or 0)
            two_weeks = int(entry.get("playtime_2weeks") or 0)

            game = db.scalar(select(Game).where(Game.steam_app_id == app_id))
            if game is None:
                game = db.scalar(select(Game).where(Game.name_key == normalize_name(name)))

            if game is None:
                game = Game(
                    name=name,
                    name_key=normalize_name(name),
                    steam_app_id=app_id,
                )
                db.add(game)
                db.flush()
                created += 1
            else:
                updated += 1
                if game.steam_app_id is None:
                    conflict = db.scalar(select(Game).where(Game.steam_app_id == app_id))
                    if conflict is None:
                        game.steam_app_id = app_id

            latest_snapshot = db.scalar(
                select(PlaytimeSnapshot)
                .where(PlaytimeSnapshot.game_id == game.id)
                .order_by(PlaytimeSnapshot.captured_at.desc())
                .limit(1)
            )

            if latest_snapshot is None:
                db.add(
                    PlaytimeSnapshot(
                        game_id=game.id, total_minutes=total, captured_at=now
                    )
                )
            elif total > latest_snapshot.total_minutes:
                delta_minutes = total - latest_snapshot.total_minutes
                # Les deltas Steam sont approximatifs : on les rattache à la
                # fenêtre qui se termine maintenant (sync toutes les 15 min).
                started_at = now - timedelta(minutes=delta_minutes)
                agent_overlap = db.scalar(
                    select(GameSession.id)
                    .where(
                        GameSession.game_id == game.id,
                        GameSession.source == "agent",
                        GameSession.started_at <= now,
                        or_(
                            GameSession.ended_at.is_(None),
                            GameSession.ended_at >= started_at,
                        ),
                    )
                    .limit(1)
                )
                if agent_overlap is None:
                    db.add(
                        GameSession(
                            game_id=game.id,
                            source="steam",
                            started_at=started_at,
                            ended_at=now,
                            last_heartbeat_at=now,
                            duration_seconds=delta_minutes * 60,
                        )
                    )
                    sessions_created += 1
                else:
                    logger.debug(
                        "Delta Steam ignoré pour %s : déjà couvert par l'agent.",
                        game.name,
                    )
                db.add(
                    PlaytimeSnapshot(
                        game_id=game.id, total_minutes=total, captured_at=now
                    )
                )
            elif total < latest_snapshot.total_minutes:
                # Le temps a baissé (remise à zéro / correction Steam) : on
                # rebase le suivi sans créer de session négative.
                db.add(
                    PlaytimeSnapshot(
                        game_id=game.id, total_minutes=total, captured_at=now
                    )
                )

            game.steam_playtime_minutes = total
            game.steam_playtime_2weeks = two_weeks
            last_played = _timestamp(int(entry.get("rtime_last_played") or 0))
            if last_played is not None:
                game.last_steam_play_at = last_played

            stale_achievements = (
                game.achievements_updated_at is None
                or (
                    ensure_utc(game.achievements_updated_at) or now
                ) < now - timedelta(hours=6)
            )
            if total > 0 and stale_achievements:
                achievement_candidates.append(game)

        db.flush()

        achievement_candidates.sort(key=_achievement_key, reverse=True)
        achievements_synced = 0
        for game in achievement_candidates[: max(0, settings.steam_achievement_limit)]:
            if game.steam_app_id is None:
                continue
            try:
                result = collector.achievements(game.steam_app_id)
            except SteamError as exc:
                logger.debug("Succès indisponibles pour %s : %s", game.name, exc)
                result = None
            if result is not None:
                game.achievements_total, game.achievements_unlocked = result
            game.achievements_updated_at = now
            achievements_synced += 1

    db.commit()
    return {
        "skipped": False,
        "created": created,
        "updated": updated,
        "sessions_created": sessions_created,
        "achievements_synced": achievements_synced,
    }
