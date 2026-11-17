from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from models import Agent, Game, GameSession, utcnow
from serializers import game_payload, session_payload
from utils import get_zone, overlap_seconds, session_bounds, session_seconds


def build_summary(db: Session, tz_name: str) -> dict:
    now = utcnow()
    zone: ZoneInfo = get_zone(tz_name)
    local_now = now.astimezone(zone)
    today_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_local = today_local - timedelta(days=local_now.weekday())
    today_start = today_local.astimezone(timezone.utc)
    week_start = week_local.astimezone(timezone.utc)

    week_sessions = db.scalars(
        select(GameSession)
        .where(
            or_(GameSession.ended_at.is_(None), GameSession.ended_at >= week_start),
            GameSession.started_at <= now,
        )
        .options(joinedload(GameSession.game))
    ).all()

    today_seconds = 0
    week_seconds = 0
    sessions_week = 0
    games_week: set[int] = set()
    for session in week_sessions:
        seconds = overlap_seconds(session, week_start, now, now)
        if seconds > 0:
            sessions_week += 1
            games_week.add(session.game_id)
            week_seconds += seconds
        today_seconds += overlap_seconds(session, today_start, now, now)

    closed_total = db.scalar(
        select(func.coalesce(func.sum(GameSession.duration_seconds), 0)).where(
            GameSession.ended_at.is_not(None)
        )
    )
    live_sessions = db.scalars(
        select(GameSession).where(GameSession.ended_at.is_(None))
    ).all()
    total_seconds = int(closed_total or 0) + sum(session_seconds(s, now) for s in live_sessions)

    agents_online = db.scalar(
        select(func.count(Agent.agent_id)).where(
            Agent.last_seen_at >= now - timedelta(minutes=10)
        )
    )
    agents_total = db.scalar(select(func.count(Agent.agent_id)))
    library_count = db.scalar(select(func.count(Game.id)))

    return {
        "today_seconds": today_seconds,
        "week_seconds": week_seconds,
        "total_seconds": total_seconds,
        "sessions_week": sessions_week,
        "distinct_games_week": len(games_week),
        "active_count": len(live_sessions),
        "library_count": int(library_count or 0),
        "agents_online": int(agents_online or 0),
        "agents_total": int(agents_total or 0),
    }


def build_heatmap(db: Session, tz_name: str, days: int = 365) -> dict:
    now = utcnow()
    zone: ZoneInfo = get_zone(tz_name)
    start = now - timedelta(days=days)

    sessions = db.scalars(
        select(GameSession).where(
            or_(GameSession.ended_at.is_(None), GameSession.ended_at >= start),
            GameSession.started_at <= now,
        )
    ).all()

    matrix = [[0.0 for _ in range(24)] for _ in range(7)]

    for session in sessions:
        session_start, session_end = session_bounds(session, now)
        cursor = max(session_start, start)
        end = min(session_end, now)

        while cursor < end:
            local_cursor = cursor.astimezone(zone)
            next_hour_local = local_cursor.replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)
            chunk_end = min(end, next_hour_local.astimezone(timezone.utc))
            if chunk_end <= cursor:
                chunk_end = end
            matrix[local_cursor.weekday()][local_cursor.hour] += (
                chunk_end - cursor
            ).total_seconds()
            cursor = chunk_end

    cells = [
        {"weekday": weekday, "hour": hour, "seconds": int(seconds)}
        for weekday, hours in enumerate(matrix)
        for hour, seconds in enumerate(hours)
    ]
    max_seconds = max((cell["seconds"] for cell in cells), default=0)

    return {"days": days, "max_seconds": max_seconds, "cells": cells}


def build_daily(db: Session, tz_name: str, days: int = 14) -> dict:
    now = utcnow()
    zone: ZoneInfo = get_zone(tz_name)
    local_today = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    first_day = local_today - timedelta(days=days - 1)
    start = first_day.astimezone(timezone.utc)

    sessions = db.scalars(
        select(GameSession).where(
            or_(GameSession.ended_at.is_(None), GameSession.ended_at >= start),
            GameSession.started_at <= now,
        )
    ).all()

    totals: dict[str, float] = {
        (first_day + timedelta(days=offset)).date().isoformat(): 0.0
        for offset in range(days)
    }

    for session in sessions:
        session_start, session_end = session_bounds(session, now)
        cursor = max(session_start, start)
        end = min(session_end, now)

        while cursor < end:
            local_cursor = cursor.astimezone(zone)
            next_midnight = (
                local_cursor.replace(hour=0, minute=0, second=0, microsecond=0)
                + timedelta(days=1)
            ).astimezone(timezone.utc)
            chunk_end = min(end, next_midnight)
            if chunk_end <= cursor:
                chunk_end = end

            key = local_cursor.date().isoformat()
            if key in totals:
                totals[key] += (chunk_end - cursor).total_seconds()
            cursor = chunk_end

    items = [
        {"date": date, "seconds": int(seconds)} for date, seconds in totals.items()
    ]
    return {
        "days": days,
        "max_seconds": max((item["seconds"] for item in items), default=0),
        "items": items,
    }


def build_top_games(db: Session, days: int, limit: int) -> list[dict]:
    now = utcnow()
    start = now - timedelta(days=days)

    sessions = db.scalars(
        select(GameSession).where(
            or_(GameSession.ended_at.is_(None), GameSession.ended_at >= start),
            GameSession.started_at <= now,
        )
    ).all()

    totals: dict[int, int] = {}
    for session in sessions:
        seconds = overlap_seconds(session, start, now, now)
        if seconds > 0:
            totals[session.game_id] = totals.get(session.game_id, 0) + seconds

    if not totals:
        return []

    top_ids = sorted(totals, key=lambda game_id: totals[game_id], reverse=True)[:limit]
    games = db.scalars(select(Game).where(Game.id.in_(top_ids))).all()
    games_by_id = {game.id: game for game in games}

    result: list[dict] = []
    for game_id in top_ids:
        game = games_by_id.get(game_id)
        if game is None:
            continue
        payload = game_payload(game)
        payload["tracked_seconds"] = totals[game_id]
        result.append(payload)
    return result


def build_recent_sessions(db: Session, limit: int, game_id: int | None = None) -> list[dict]:
    query = (
        select(GameSession)
        .options(joinedload(GameSession.game))
        .order_by(GameSession.started_at.desc())
        .limit(limit)
    )
    if game_id is not None:
        query = query.where(GameSession.game_id == game_id)

    sessions = db.scalars(query).all()
    return [session_payload(session) for session in sessions]


def build_library(db: Session, search: str | None, sort: str, limit: int) -> list[dict]:
    query = select(Game)
    if search:
        query = query.where(Game.name.ilike(f"%{search}%"))

    if sort == "name":
        query = query.order_by(Game.name.asc())
    elif sort == "recent":
        query = query.order_by(Game.last_steam_play_at.desc().nullslast(), Game.name.asc())
    else:
        query = query.order_by(Game.steam_playtime_minutes.desc(), Game.name.asc())

    games = db.scalars(query.limit(limit)).all()
    return [game_payload(game) for game in games]
