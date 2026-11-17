from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import GameSession, utcnow
from settings_service import get_homepage_api_token, get_timezone_name
from stats import build_summary, build_top_games
from utils import iso_utc

router = APIRouter(prefix="/api/homepage", tags=["homepage"])


def _short_duration(seconds: int) -> str:
    minutes = max(0, seconds) // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, remaining = divmod(minutes, 60)
    return f"{hours}h {remaining:02d}m"


def _authorize(
    db: Session,
    query_token: str | None,
    header_token: str | None,
) -> None:
    expected = get_homepage_api_token(db)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le token Homepage n'est pas configuré.",
        )
    candidate = header_token or query_token
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Homepage invalide.",
        )


@router.get("")
def homepage_widget(
    token: str | None = Query(default=None),
    x_api_key: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> dict:
    _authorize(db, token, x_api_key)

    summary = build_summary(db, get_timezone_name(db))
    top_games = build_top_games(db, days=30, limit=1)
    live_sessions = db.scalars(
        select(GameSession)
        .options(joinedload(GameSession.game))
        .where(GameSession.ended_at.is_(None))
        .order_by(GameSession.started_at)
    ).all()

    active_games = ", ".join(
        session.game.name for session in live_sessions if session.game is not None
    )
    now = utcnow()

    return {
        "status": "ok",
        "today_seconds": summary["today_seconds"],
        "week_seconds": summary["week_seconds"],
        "total_seconds": summary["total_seconds"],
        "today": _short_duration(summary["today_seconds"]),
        "week": _short_duration(summary["week_seconds"]),
        "total": _short_duration(summary["total_seconds"]),
        "sessions_week": summary["sessions_week"],
        "active_sessions": summary["active_count"],
        "active_games": active_games or "—",
        "library_count": summary["library_count"],
        "agents_online": summary["agents_online"],
        "top_game": top_games[0]["name"] if top_games else "—",
        "updated_at": iso_utc(now),
    }
