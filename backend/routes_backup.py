from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import Boolean, Integer
from starlette.background import BackgroundTask

from database import SessionLocal, engine
from models import Base
from security import AdminUser
from settings_service import ensure_default_settings

router = APIRouter(prefix="/api/admin/backup", tags=["backup"])

BACKUP_FORMAT = "gamestats-backup"
BACKUP_VERSION = 1

# Sessions are intentionally excluded: restoring a backup must not restore
# browser sessions from another point in time.
BACKUP_TABLES = [
    "users",
    "games",
    "agents",
    "playtime_snapshots",
    "sessions",
    "app_settings",
]
DELETE_ORDER = [
    "auth_sessions",
    "sessions",
    "playtime_snapshots",
    "games",
    "agents",
    "app_settings",
    "users",
]

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _database_path() -> Path:
    if not engine.url.database or engine.url.drivername != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette fonctionnalité est disponible uniquement avec SQLite.",
        )
    return Path(engine.url.database).resolve()


def _table_columns(table_name: str) -> list[str]:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Table inconnue : {table_name}",
        )
    return [column.name for column in table.columns]


def _export_tables() -> dict[str, list[dict[str, Any]]]:
    path = _database_path()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables: dict[str, list[dict[str, Any]]] = {}
        for table_name in BACKUP_TABLES:
            rows = connection.execute(f'SELECT * FROM "{table_name}"').fetchall()
            tables[table_name] = [dict(row) for row in rows]
        return tables
    finally:
        connection.close()


def _validate_backup_tables(tables: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(tables, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier de sauvegarde ne contient pas de tables valides.",
        )

    normalized: dict[str, list[dict[str, Any]]] = {}
    for table_name in BACKUP_TABLES:
        rows = tables.get(table_name)
        if not isinstance(rows, list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Table manquante ou invalide : {table_name}",
            )
        normalized[table_name] = []
        for row in rows:
            if not isinstance(row, dict):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Ligne invalide dans la table {table_name}.",
                )
            normalized[table_name].append(row)

    active_admins = [
        row
        for row in normalized["users"]
        if row.get("role") == "admin" and bool(row.get("is_active"))
    ]
    if not active_admins:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La sauvegarde ne contient aucun administrateur actif.",
        )
    return normalized


def _restore_tables(tables: dict[str, list[dict[str, Any]]]) -> None:
    path = _database_path()
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN")
        for table_name in DELETE_ORDER:
            connection.execute(f'DELETE FROM "{table_name}"')

        for table_name in BACKUP_TABLES:
            table = Base.metadata.tables[table_name]
            columns = [column.name for column in table.columns]
            placeholders = ", ".join("?" for _ in columns)
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            rows = tables[table_name]
            for row in rows:
                values = []
                for column in table.columns:
                    if column.name in row:
                        values.append(row[column.name])
                    elif column.default is not None and getattr(
                        column.default, "is_scalar", False
                    ):
                        values.append(column.default.arg)
                    elif column.nullable:
                        values.append(None)
                    elif isinstance(column.type, Boolean):
                        values.append(False)
                    elif isinstance(column.type, Integer):
                        values.append(0)
                    else:
                        values.append("")
                connection.execute(
                    f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})',
                    values,
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.close()

    # Keep defaults available if an old backup did not contain settings.
    with SessionLocal() as db:
        ensure_default_settings(db)


def _json_response(tables: dict[str, list[dict[str, Any]]]) -> JSONResponse:
    payload = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }
    filename = f"gamestats-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/json")
def export_json(_admin: AdminUser) -> JSONResponse:
    return _json_response(_export_tables())


@router.get("/export/sqlite")
def export_sqlite(_admin: AdminUser) -> FileResponse:
    path = _database_path()
    backup_path = path.parent / f".gamestats-backup-{uuid.uuid4().hex}.db"
    source = sqlite3.connect(path)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    filename = f"gamestats-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
    return FileResponse(
        path=backup_path,
        media_type="application/vnd.sqlite3",
        filename=filename,
        background=BackgroundTask(backup_path.unlink, missing_ok=True),
    )


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Le fichier de sauvegarde dépasse la limite de 100 Mo.",
        )
    return content


@router.post("/import/json")
async def import_json(
    _admin: AdminUser,
    file: UploadFile = File(...),
) -> dict:
    content = await _read_upload(file)
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fichier JSON invalide.",
        ) from exc

    if not isinstance(payload, dict) or payload.get("format") != BACKUP_FORMAT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ce fichier n'est pas une sauvegarde GameStats.",
        )
    if payload.get("version") != BACKUP_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Version de sauvegarde non prise en charge.",
        )

    tables = _validate_backup_tables(payload.get("tables"))
    _restore_tables(tables)
    return {
        "ok": True,
        "message": "Sauvegarde restaurée. Reconnectez-vous.",
    }


@router.post("/restore/sqlite")
async def restore_sqlite(
    _admin: AdminUser,
    file: UploadFile = File(...),
) -> dict:
    content = await _read_upload(file)
    if not content.startswith(b"SQLite format 3\x00"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fichier n'est pas une base SQLite valide.",
        )

    fd, temp_name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        temp_path.write_bytes(content)
        source = sqlite3.connect(temp_path)
        source.row_factory = sqlite3.Row
        try:
            integrity = source.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="La base SQLite est corrompue.",
                )

            existing_tables = {
                row["name"]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = set(BACKUP_TABLES) - existing_tables
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Tables manquantes dans la sauvegarde : {', '.join(sorted(missing))}",
                )

            tables: dict[str, list[dict[str, Any]]] = {}
            for table_name in BACKUP_TABLES:
                rows = source.execute(f'SELECT * FROM "{table_name}"').fetchall()
                tables[table_name] = [dict(row) for row in rows]
        finally:
            source.close()

        normalized = _validate_backup_tables(tables)
        _restore_tables(normalized)
        return {
            "ok": True,
            "message": "Base SQLite restaurée. Reconnectez-vous.",
        }
    finally:
        temp_path.unlink(missing_ok=True)
