from __future__ import annotations

import json

from models import Game, GameSession
from utils import iso_utc, session_seconds


def parse_genres(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def game_payload(game: Game) -> dict:
    return {
        "id": game.id,
        "name": game.name,
        "steam_app_id": game.steam_app_id,
        "xbox_title_id": game.xbox_title_id,
        "cover_url": game.cover_url,
        "genres": parse_genres(game.genres),
        "steam_playtime_minutes": game.steam_playtime_minutes or 0,
        "playtime_2weeks_minutes": game.steam_playtime_2weeks or 0,
        "achievements_total": game.achievements_total or 0,
        "achievements_unlocked": game.achievements_unlocked or 0,
        "last_played_at": iso_utc(game.last_steam_play_at),
        "xbox_achievements_total": game.xbox_achievements_total or 0,
        "xbox_achievements_unlocked": game.xbox_achievements_unlocked or 0,
        "xbox_gamerscore": game.xbox_gamerscore or 0,
        "xbox_gamerscore_total": game.xbox_gamerscore_total or 0,
        "xbox_last_played_at": iso_utc(game.xbox_last_played_at),
        "ubisoft_space_id": game.ubisoft_space_id,
        "ubisoft_sessions_count": game.ubisoft_sessions_count or 0,
        "ubisoft_first_played_at": iso_utc(game.ubisoft_first_played_at),
        "ubisoft_last_played_at": iso_utc(game.ubisoft_last_played_at),
    }


def session_payload(session: GameSession) -> dict:
    return {
        "id": session.id,
        "game_id": session.game_id,
        "game_name": session.game.name,
        "cover_url": session.game.cover_url,
        "source": session.source,
        "agent_id": session.agent_id,
        "started_at": iso_utc(session.started_at),
        "ended_at": iso_utc(session.ended_at),
        "duration_seconds": session_seconds(session),
        "is_live": session.ended_at is None,
    }
