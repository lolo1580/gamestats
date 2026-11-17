from __future__ import annotations

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from collectors.epic import sync_epic_library
from collectors.gog import sync_gog_library
from collectors.igdb import enrich_games
from collectors.steam import sync_steam_library
from collectors.ubisoft import sync_ubisoft_library
from collectors.xbox import sync_xbox_library
from config import get_settings
from database import SessionLocal
from heartbeat import close_stale_agent_sessions
from influx import export_to_influx
from models import utcnow

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _sweep_job() -> None:
    settings = get_settings()
    try:
        with SessionLocal() as db:
            close_stale_agent_sessions(db, settings.agent_stale_seconds)
    except Exception:
        logger.exception("Échec du nettoyage des sessions inactives.")


def _steam_job() -> None:
    try:
        with SessionLocal() as db:
            result = sync_steam_library(db)
            if result.get("skipped"):
                logger.info("Sync Steam ignorée : %s", result.get("reason"))
            else:
                logger.info(
                    "Sync Steam terminée : %s nouveau(x), %s mis à jour, %s session(s).",
                    result.get("created", 0),
                    result.get("updated", 0),
                    result.get("sessions_created", 0),
                )
    except Exception:
        logger.exception("Échec de la synchronisation Steam.")


def _igdb_job() -> None:
    try:
        with SessionLocal() as db:
            result = enrich_games(db)
            if result.get("skipped"):
                logger.info("Enrichissement IGDB ignoré : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de l'enrichissement IGDB.")


def _influx_job() -> None:
    try:
        with SessionLocal() as db:
            result = export_to_influx(db)
            if result.get("skipped"):
                logger.debug("Export InfluxDB ignoré : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de l'export InfluxDB.")


def _xbox_job() -> None:
    try:
        with SessionLocal() as db:
            result = sync_xbox_library(db)
            if result.get("skipped"):
                logger.debug("Sync Xbox ignorée : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de la synchronisation Xbox.")


def _ubisoft_job() -> None:
    try:
        with SessionLocal() as db:
            result = sync_ubisoft_library(db)
            if result.get("skipped"):
                logger.debug("Sync Ubisoft ignorée : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de la synchronisation Ubisoft.")


def _gog_job() -> None:
    try:
        with SessionLocal() as db:
            result = sync_gog_library(db)
            if result.get("skipped"):
                logger.debug("Sync GOG ignorée : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de la synchronisation GOG.")


def _epic_job() -> None:
    try:
        with SessionLocal() as db:
            result = sync_epic_library(db)
            if result.get("skipped"):
                logger.debug("Sync Epic Games ignorée : %s", result.get("reason"))
    except Exception:
        logger.exception("Échec de la synchronisation Epic Games.")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )

    scheduler.add_job(
        _sweep_job,
        IntervalTrigger(seconds=60),
        id="sweep-sessions",
        name="Clôture des sessions agent inactives",
    )

    scheduler.add_job(
        _steam_job,
        IntervalTrigger(minutes=max(5, settings.steam_sync_minutes)),
        id="sync-steam",
        name="Synchronisation Steam",
        next_run_time=utcnow() + timedelta(seconds=10),
    )
    scheduler.add_job(
        _igdb_job,
        IntervalTrigger(minutes=max(15, settings.igdb_sync_minutes)),
        id="enrich-igdb",
        name="Enrichissement IGDB",
        next_run_time=utcnow() + timedelta(seconds=30),
    )
    scheduler.add_job(
        _influx_job,
        IntervalTrigger(minutes=max(5, settings.influx_export_minutes)),
        id="export-influxdb",
        name="Export InfluxDB",
        next_run_time=utcnow() + timedelta(seconds=45),
    )
    scheduler.add_job(
        _xbox_job,
        IntervalTrigger(minutes=max(10, settings.xbox_sync_minutes)),
        id="sync-xbox",
        name="Synchronisation Xbox",
        next_run_time=utcnow() + timedelta(seconds=60),
    )
    scheduler.add_job(
        _ubisoft_job,
        IntervalTrigger(minutes=max(15, settings.ubisoft_sync_minutes)),
        id="sync-ubisoft",
        name="Synchronisation Ubisoft",
        next_run_time=utcnow() + timedelta(seconds=75),
    )
    scheduler.add_job(
        _gog_job,
        IntervalTrigger(minutes=max(30, settings.gog_sync_minutes)),
        id="sync-gog",
        name="Synchronisation GOG",
        next_run_time=utcnow() + timedelta(seconds=90),
    )
    scheduler.add_job(
        _epic_job,
        IntervalTrigger(minutes=max(60, settings.epic_sync_minutes)),
        id="sync-epic",
        name="Synchronisation Epic Games",
        next_run_time=utcnow() + timedelta(seconds=105),
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Planificateur démarré (Steam: %s min, IGDB: %s min, InfluxDB: %s min, Xbox: %s min, Ubisoft: %s min, GOG: %s min, Epic: %s min, configuration via /api/settings).",
        max(5, settings.steam_sync_minutes),
        max(15, settings.igdb_sync_minutes),
        max(5, settings.influx_export_minutes),
        max(10, settings.xbox_sync_minutes),
        max(15, settings.ubisoft_sync_minutes),
        max(30, settings.gog_sync_minutes),
        max(60, settings.epic_sync_minutes),
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Planificateur arrêté.")
