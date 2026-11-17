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
BUNDLED_DOWNLOADS_DIR = Path("/opt/agent-downloads")


def _release_candidates(name: str) -> list[Path]:
    configured = Path(get_settings().downloads_dir).expanduser()
    directories = [configured]
    if BUNDLED_DOWNLOADS_DIR != configured:
        directories.append(BUNDLED_DOWNLOADS_DIR)
    return [directory / name for directory in directories]


def _file_size(path: Path) -> int | None:
    try:
        if not path.is_file():
            return None
        size = path.stat().st_size
        return size if size > 0 else None
    except OSError:
        return None


def _release_info(name: str) -> tuple[Path | None, int | None]:
    for path in _release_candidates(name):
        size = _file_size(path)
        if size is not None:
            return path, size
    return None, None


@router.get("/release", response_model=AgentReleaseOut)
def read_agent_release(_admin: AdminUser) -> dict:
    _, installer_size = _release_info(INSTALLER_NAME)
    _, portable_size = _release_info(PORTABLE_NAME)
    return {
        "installer_available": installer_size is not None,
        "installer_size": installer_size,
        "portable_available": portable_size is not None,
        "portable_size": portable_size,
    }


@router.get("/download/installer", response_class=FileResponse)
def download_agent_installer(_admin: AdminUser) -> FileResponse:
    path, _ = _release_info(INSTALLER_NAME)
    if path is None:
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
    path, _ = _release_info(PORTABLE_NAME)
    if path is None:
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
