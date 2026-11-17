from __future__ import annotations

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from collectors.igdb import enrich_games
from collectors.steam import sync_steam_library
from config import get_settings
from database import SessionLocal
from heartbeat import close_stale_agent_sessions
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

    if settings.steam_configured:
        scheduler.add_job(
            _steam_job,
            IntervalTrigger(minutes=max(5, settings.steam_sync_minutes)),
            id="sync-steam",
            name="Synchronisation Steam",
            next_run_time=utcnow() + timedelta(seconds=10),
        )
    else:
        logger.warning("Steam non configuré : la synchronisation est désactivée.")

    if settings.igdb_configured:
        scheduler.add_job(
            _igdb_job,
            IntervalTrigger(minutes=max(15, settings.igdb_sync_minutes)),
            id="enrich-igdb",
            name="Enrichissement IGDB",
            next_run_time=utcnow() + timedelta(seconds=30),
        )
    else:
        logger.warning("IGDB non configuré : les jaquettes ne seront pas enrichies.")

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Planificateur démarré (Steam: %s, IGDB: %s).",
        "oui" if settings.steam_configured else "non",
        "oui" if settings.igdb_configured else "non",
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Planificateur arrêté.")
