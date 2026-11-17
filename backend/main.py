from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from auth import require_agent_key
from collectors.igdb import IGDBError, enrich_games
from collectors.steam import SteamError, sync_steam_library
from config import get_settings
from database import SessionLocal, get_db, init_db
from heartbeat import process_heartbeat
from models import Agent, User, utcnow
from routes_auth import router as auth_router
from routes_backup import router as backup_router
from routes_homepage import router as homepage_router
from routes_influx import router as influx_router
from routes_settings import router as settings_router
from routes_users import router as users_router
from routes_xbox import router as xbox_router
from scheduler import start_scheduler, stop_scheduler
from schemas import (
    DailyStatsOut,
    GameOut,
    HeatmapOut,
    HeartbeatIn,
    HeartbeatOut,
    SessionOut,
    SummaryOut,
    SyncResultOut,
    TopGameOut,
)
from security import AdminUser, CurrentUser
from settings_service import (
    ensure_default_settings,
    get_agent_api_key,
    get_integration_settings,
    get_timezone_name,
)
from stats import (
    build_daily,
    build_heatmap,
    build_library,
    build_recent_sessions,
    build_summary,
    build_top_games,
)
from utils import ensure_utc, iso_utc

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Base de données initialisée (%s).", settings.database_url)
    with SessionLocal() as db:
        ensure_default_settings(db)
        if get_agent_api_key(db) == "change-me":
            logger.warning(
                "La clé agent utilise la valeur par défaut 'change-me' : "
                "changez-la dans les paramètres avant toute exposition réseau."
            )
        if (db.scalar(select(func.count(User.id))) or 0) == 0:
            logger.warning("Aucun utilisateur : l'assistant d'installation initiale est requis.")
    if settings.scheduler_enabled:
        try:
            start_scheduler()
        except Exception:
            logger.exception("Impossible de démarrer le planificateur.")
    yield
    stop_scheduler()


app = FastAPI(
    title="GameStats API",
    version="1.3.0",
    description="Suivi de sessions de jeu (agent PC + Steam) et statistiques.",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(homepage_router)
app.include_router(influx_router)
app.include_router(xbox_router)


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        logger.exception("Healthcheck base de données en échec.")
        database_ok = False

    if not database_ok:
        raise HTTPException(status_code=503, detail="Base de données indisponible.")

    integration = get_integration_settings(db)
    return {
        "status": "ok",
        "time": iso_utc(utcnow()),
        "steam_configured": integration.steam_configured,
        "igdb_configured": integration.igdb_configured,
        "scheduler_enabled": settings.scheduler_enabled,
        "agent_key_is_default": get_agent_api_key(db) == "change-me",
        "setup_required": (db.scalar(select(func.count(User.id))) or 0) == 0,
    }


@app.get("/api/openapi.json", include_in_schema=False)
def openapi_schema(_user: CurrentUser) -> dict:
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def swagger_docs(_user: CurrentUser):
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=f"{settings.app_name} API",
    )


@app.get("/redoc", include_in_schema=False)
def redoc_docs(_user: CurrentUser):
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title=f"{settings.app_name} API",
    )


@app.post("/api/heartbeat", response_model=HeartbeatOut)
def receive_heartbeat(
    payload: HeartbeatIn,
    db: Session = Depends(get_db),
    _auth: Annotated[None, Depends(require_agent_key)] = None,
) -> dict:
    return process_heartbeat(db, payload)


@app.get("/api/stats/summary", response_model=SummaryOut)
def stats_summary(_user: CurrentUser, db: Session = Depends(get_db)) -> dict:
    return build_summary(db, get_timezone_name(db))


@app.get("/api/stats/heatmap", response_model=HeatmapOut)
def stats_heatmap(
    _user: CurrentUser,
    days: int = Query(default=365, ge=7, le=3650),
    db: Session = Depends(get_db),
) -> dict:
    return build_heatmap(db, get_timezone_name(db), days)


@app.get("/api/stats/daily", response_model=DailyStatsOut)
def stats_daily(
    _user: CurrentUser,
    days: int = Query(default=14, ge=2, le=365),
    db: Session = Depends(get_db),
) -> dict:
    return build_daily(db, get_timezone_name(db), days)


@app.get("/api/stats/top-games", response_model=list[TopGameOut])
def stats_top_games(
    _user: CurrentUser,
    days: int = Query(default=30, ge=1, le=3650),
    limit: int = Query(default=8, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    return build_top_games(db, days, limit)


@app.get("/api/sessions", response_model=list[SessionOut])
def list_sessions(
    _user: CurrentUser,
    limit: int = Query(default=15, ge=1, le=100),
    game_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[dict]:
    return build_recent_sessions(db, limit, game_id)


@app.get("/api/games", response_model=list[GameOut])
def list_games(
    _user: CurrentUser,
    search: str | None = Query(default=None, max_length=120),
    sort: Literal["playtime", "name", "recent"] = Query(default="playtime"),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    return build_library(db, search, sort, limit)


@app.get("/api/agents")
def list_agents(_user: CurrentUser, db: Session = Depends(get_db)) -> list[dict]:
    agents = db.scalars(select(Agent).order_by(Agent.last_seen_at.desc())).all()
    now = utcnow()
    result: list[dict] = []
    for agent in agents:
        last_seen = ensure_utc(agent.last_seen_at)
        result.append(
            {
                "agent_id": agent.agent_id,
                "hostname": agent.hostname,
                "last_seen_at": iso_utc(agent.last_seen_at),
                "online": bool(last_seen and (now - last_seen).total_seconds() < 600),
            }
        )
    return result


@app.post("/api/admin/sync/steam", response_model=SyncResultOut)
def admin_sync_steam(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        return sync_steam_library(db)
    except SteamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/admin/enrich/igdb", response_model=SyncResultOut)
def admin_enrich_igdb(
    _admin: AdminUser,
    limit: int | None = Query(default=None, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return enrich_games(db, limit)
    except IGDBError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
