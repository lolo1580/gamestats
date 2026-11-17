from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from influx import InfluxError, export_to_influx
from schemas import InfluxExportOut
from security import AdminUser

router = APIRouter(prefix="/api/admin/influxdb", tags=["influxdb"])


@router.post("/export", response_model=InfluxExportOut)
def export_influx(_admin: AdminUser, db: Session = Depends(get_db)) -> dict:
    try:
        return export_to_influx(db)
    except InfluxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
