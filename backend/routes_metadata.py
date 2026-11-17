from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collectors.metadata import enrich_metadata
from database import get_db
from schemas import MetadataSyncOut
from security import AdminUser

router = APIRouter(prefix="/api/metadata", tags=["metadata"])
logger = logging.getLogger(__name__)


@router.post("/sync", response_model=MetadataSyncOut)
def sync_metadata(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    result = enrich_metadata(db)
    if result.get("skipped"):
        logger.debug("Enrichissement métadonnées ignoré : %s", result.get("reason"))
    return result
