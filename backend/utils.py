from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from models import GameSession, utcnow


def normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def ensure_utc(value: datetime | None) -> datetime | None:
    """SQLite renvoie des datetimes naïfs : on les considère comme UTC."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    normalized = ensure_utc(value)
    return normalized.isoformat() if normalized else None


def get_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def session_bounds(session: GameSession, now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or utcnow()
    start = ensure_utc(session.started_at) or current
    end = ensure_utc(session.ended_at) or current
    if end < start:
        end = start
    return start, end


def session_seconds(session: GameSession, now: datetime | None = None) -> int:
    start, end = session_bounds(session, now)
    return max(0, int((end - start).total_seconds()))


def overlap_seconds(
    session: GameSession, range_start: datetime, range_end: datetime, now: datetime | None = None
) -> int:
    start, end = session_bounds(session, now)
    low = max(start, range_start)
    high = min(end, range_end)
    if high <= low:
        return 0
    return int((high - low).total_seconds())


def close_session(session: GameSession, end: datetime) -> None:
    start = ensure_utc(session.started_at) or end
    end = max(start, end)
    session.ended_at = end
    session.duration_seconds = max(0, int((end - start).total_seconds()))


def clamp_captured_at(
    captured_at: datetime | None, now: datetime, max_skew: timedelta = timedelta(minutes=10)
) -> datetime:
    captured = ensure_utc(captured_at)
    if captured is None or captured > now + timedelta(minutes=1) or captured < now - max_skew:
        return now
    return captured
