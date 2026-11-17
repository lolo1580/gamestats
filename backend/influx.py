from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import GameSession, utcnow
from settings_service import (
    SETTING_INFLUX_LAST_EXPORT,
    get_integration_settings,
    get_setting,
    get_timezone_name,
    update_settings,
)
from stats import build_summary
from utils import ensure_utc

logger = logging.getLogger(__name__)


class InfluxError(RuntimeError):
    pass


def _escape_tag(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(" ", "\\ ")
        .replace(",", "\\,")
        .replace("=", "\\=")
    )


def _session_lines(sessions: list[GameSession]) -> list[str]:
    lines: list[str] = []
    for session in sessions:
        ended_at = ensure_utc(session.ended_at)
        if ended_at is None or session.game is None:
            continue
        game = _escape_tag(session.game.name)
        source = _escape_tag(session.source)
        duration = int(session.duration_seconds or 0)
        lines.append(
            "gamestats_session,"
            f"game={game},source={source},game_id={session.game_id} "
            f"duration_seconds={duration} "
            f"{int(ended_at.timestamp())}"
        )
    return lines


def _summary_line(db: Session, timestamp: int) -> str:
    summary = build_summary(db, get_timezone_name(db))
    return (
        "gamestats_summary "
        f"today_seconds={summary['today_seconds']},"
        f"week_seconds={summary['week_seconds']},"
        f"total_seconds={summary['total_seconds']},"
        f"sessions_week={summary['sessions_week']},"
        f"active_sessions={summary['active_count']},"
        f"library_count={summary['library_count']},"
        f"agents_online={summary['agents_online']} "
        f"{timestamp}"
    )


def export_to_influx(db: Session) -> dict:
    integration = get_integration_settings(db)
    if not integration.influxdb_enabled:
        return {"skipped": True, "reason": "Export InfluxDB désactivé."}
    if not integration.influxdb_configured:
        return {
            "skipped": True,
            "reason": "Configuration InfluxDB incomplète.",
        }

    since_raw = get_setting(db, SETTING_INFLUX_LAST_EXPORT)
    since: datetime | None = None
    if since_raw:
        try:
            since = ensure_utc(datetime.fromisoformat(since_raw))
        except ValueError:
            logger.warning("Date de dernier export InfluxDB invalide : %s", since_raw)

    query = (
        select(GameSession)
        .options(joinedload(GameSession.game))
        .where(GameSession.ended_at.is_not(None))
        .order_by(GameSession.ended_at)
    )
    if since is not None:
        query = query.where(GameSession.ended_at > since)

    sessions = db.scalars(query).all()
    now = utcnow()
    lines = _session_lines(sessions)
    lines.append(_summary_line(db, int(now.timestamp())))

    endpoint = integration.influxdb_url.rstrip("/")
    if not endpoint.endswith("/api/v2/write"):
        endpoint = f"{endpoint}/api/v2/write"

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                endpoint,
                params={
                    "org": integration.influxdb_org,
                    "bucket": integration.influxdb_bucket,
                    "precision": "s",
                },
                headers={
                    "Authorization": f"Token {integration.influxdb_token}",
                    "Content-Type": "text/plain; charset=utf-8",
                },
                content="\n".join(lines),
            )
    except httpx.HTTPError as exc:
        raise InfluxError(f"InfluxDB injoignable : {exc}") from exc

    if response.status_code not in {200, 204}:
        detail = " ".join(response.text.split())[:300]
        raise InfluxError(f"InfluxDB {response.status_code} : {detail}")

    update_settings(db, {SETTING_INFLUX_LAST_EXPORT: now.isoformat()})
    logger.info(
        "Export InfluxDB : %s session(s), %s point(s).",
        len(sessions),
        len(lines),
    )
    return {
        "skipped": False,
        "sessions_exported": len(sessions),
        "points_written": len(lines),
        "last_export_at": now.isoformat(),
    }
