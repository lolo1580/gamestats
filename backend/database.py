from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")


def _ensure_sqlite_directory(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw_path = url.removeprefix("sqlite:///").split("?", 1)[0]
    if raw_path in {"", ":memory:"}:
        return
    Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # L'import enregistre les modèles sur Base.metadata.
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Lightweight migrations for columns added after the first release.

    ``create_all`` creates missing tables but never adds columns to existing
    tables. SQLite is the supported database, so a targeted ALTER is enough.
    """

    if not _is_sqlite:
        return
    inspector = inspect(engine)
    if "games" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("games")}
    additions = {
        "xbox_title_id": "VARCHAR(32)",
        "xbox_achievements_total": "INTEGER NOT NULL DEFAULT 0",
        "xbox_achievements_unlocked": "INTEGER NOT NULL DEFAULT 0",
        "xbox_gamerscore": "INTEGER NOT NULL DEFAULT 0",
        "xbox_gamerscore_total": "INTEGER NOT NULL DEFAULT 0",
        "xbox_last_played_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.exec_driver_sql(f'ALTER TABLE games ADD COLUMN "{name}" {ddl}')
        connection.exec_driver_sql(
            'CREATE UNIQUE INDEX IF NOT EXISTS "ix_games_xbox_title_id" '
            'ON "games" ("xbox_title_id")'
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
