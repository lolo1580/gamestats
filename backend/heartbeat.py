from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Agent, Game, GameSession, utcnow
from schemas import HeartbeatIn
from utils import clamp_captured_at, close_session, ensure_utc, normalize_name

logger = logging.getLogger(__name__)


def _resolve_game(db: Session, item) -> Game:
    game: Game | None = None

    if item.steam_app_id:
        game = db.scalar(select(Game).where(Game.steam_app_id == item.steam_app_id))

    name_key = normalize_name(item.name)
    if game is None:
        game = db.scalar(select(Game).where(Game.name_key == name_key))

    if game is None:
        game = Game(
            name=item.name.strip(),
            name_key=name_key,
            steam_app_id=item.steam_app_id,
        )
        db.add(game)
        db.flush()
        return game

    if item.steam_app_id and game.steam_app_id is None:
        conflict = db.scalar(select(Game).where(Game.steam_app_id == item.steam_app_id))
        if conflict is None:
            game.steam_app_id = item.steam_app_id

    return game


def process_heartbeat(db: Session, payload: HeartbeatIn, now: datetime | None = None) -> dict:
    """Crée / prolonge / clôture les sessions d'un agent à partir d'un heartbeat."""

    current = now or utcnow()
    captured = clamp_captured_at(payload.captured_at, current)

    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        agent = Agent(agent_id=payload.agent_id, hostname=payload.hostname, last_seen_at=current)
        db.add(agent)
    else:
        agent.last_seen_at = current
        if payload.hostname:
            agent.hostname = payload.hostname

    open_sessions = db.scalars(
        select(GameSession)
        .where(
            GameSession.agent_id == payload.agent_id,
            GameSession.ended_at.is_(None),
        )
        .order_by(GameSession.started_at)
    ).all()

    active_by_game: dict[int, GameSession] = {}
    for session in open_sessions:
        if session.game_id in active_by_game:
            # Nettoyage d'un éventuel doublon (redémarrage brutal, etc.).
            close_session(session, ensure_utc(session.last_heartbeat_at) or current)
        else:
            active_by_game[session.game_id] = session

    incoming: dict[int, GameSession] = {}
    for item in payload.games:
        game = _resolve_game(db, item)
        if game.id in incoming:
            continue

        session = active_by_game.get(game.id)
        if session is None:
            session = GameSession(
                game_id=game.id,
                agent_id=payload.agent_id,
                source="agent",
                started_at=captured,
                last_heartbeat_at=current,
            )
            db.add(session)
            db.flush()
            session.game = game
        else:
            session.last_heartbeat_at = current

        incoming[game.id] = session

    for game_id, session in active_by_game.items():
        if game_id in incoming:
            continue
        end = ensure_utc(session.last_heartbeat_at) or current
        close_session(session, min(end, current))

    db.commit()

    return {
        "accepted": True,
        "received_at": current,
        "active_sessions": [
            {
                "id": session.id,
                "game_id": session.game_id,
                "game_name": session.game.name,
                "started_at": session.started_at,
            }
            for session in incoming.values()
        ],
    }


def close_stale_agent_sessions(
    db: Session, stale_seconds: int, now: datetime | None = None
) -> int:
    current = now or utcnow()
    cutoff = current - timedelta(seconds=stale_seconds)

    stale = db.scalars(
        select(GameSession).where(
            GameSession.ended_at.is_(None),
            GameSession.source == "agent",
            GameSession.last_heartbeat_at.is_not(None),
            GameSession.last_heartbeat_at < cutoff,
        )
    ).all()

    for session in stale:
        close_session(session, ensure_utc(session.last_heartbeat_at) or current)

    if stale:
        db.commit()
        logger.info("%s session(s) agent clôturée(s) pour inactivité.", len(stale))

    return len(stale)
