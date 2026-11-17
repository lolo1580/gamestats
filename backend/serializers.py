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
        "gog_product_id": game.gog_product_id,
        "gog_achievements_total": game.gog_achievements_total or 0,
        "gog_achievements_unlocked": game.gog_achievements_unlocked or 0,
        "epic_catalog_item_id": game.epic_catalog_item_id,
        "epic_achievements_total": game.epic_achievements_total or 0,
        "epic_achievements_unlocked": game.epic_achievements_unlocked or 0,
        "release_date": game.release_date,
        "mobygames_id": game.mobygames_id,
        "mobygames_url": game.mobygames_url,
        "mobygames_score": game.mobygames_score,
        "mobygames_num_votes": game.mobygames_num_votes or 0,
        "opencritic_id": game.opencritic_id,
        "opencritic_url": game.opencritic_url,
        "opencritic_score": game.opencritic_score,
        "opencritic_tier": game.opencritic_tier,
        "opencritic_reviews": game.opencritic_reviews or 0,
        "opencritic_recommended": game.opencritic_recommended,
        "hltb_id": game.hltb_id,
        "hltb_url": game.hltb_url,
        "hltb_main_minutes": game.hltb_main_minutes or 0,
        "hltb_main_extra_minutes": game.hltb_main_extra_minutes or 0,
        "hltb_completionist_minutes": game.hltb_completionist_minutes or 0,
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
