from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import get_settings
from schemas import AgentReleaseOut
from security import AdminUser

router = APIRouter(prefix="/api/agent", tags=["agent"])

INSTALLER_NAME = "GameStatsAgentSetup.exe"
PORTABLE_NAME = "GameStatsAgent-portable.zip"


def _release_path(name: str) -> Path:
    return Path(get_settings().downloads_dir).expanduser() / name


def _file_size(path: Path) -> int | None:
    try:
        if not path.is_file():
            return None
        size = path.stat().st_size
        return size if size > 0 else None
    except OSError:
        return None


@router.get("/release", response_model=AgentReleaseOut)
def read_agent_release(_admin: AdminUser) -> dict:
    installer = _release_path(INSTALLER_NAME)
    portable = _release_path(PORTABLE_NAME)
    installer_size = _file_size(installer)
    portable_size = _file_size(portable)
    return {
        "installer_available": installer_size is not None,
        "installer_size": installer_size,
        "portable_available": portable_size is not None,
        "portable_size": portable_size,
    }


@router.get("/download/installer", response_class=FileResponse)
def download_agent_installer(_admin: AdminUser) -> FileResponse:
    path = _release_path(INSTALLER_NAME)
    if _file_size(path) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Installateur indisponible. Placez GameStatsAgentSetup.exe "
                "dans le dossier downloads/ du serveur."
            ),
        )
    return FileResponse(
        path,
        media_type="application/vnd.microsoft.portable-executable",
        filename=INSTALLER_NAME,
    )


@router.get("/download/portable", response_class=FileResponse)
def download_agent_portable(_admin: AdminUser) -> FileResponse:
    path = _release_path(PORTABLE_NAME)
    if _file_size(path) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Archive portable indisponible. Placez "
                "GameStatsAgent-portable.zip dans le dossier downloads/ du serveur."
            ),
        )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=PORTABLE_NAME,
    )
