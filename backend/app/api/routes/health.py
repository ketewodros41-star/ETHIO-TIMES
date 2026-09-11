"""Service health and per-source health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.source import SourceHealthRead
from app.services.source_service import SourceService

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.project_name,
        "environment": settings.environment,
        "database": "ok" if db_ok else "error",
    }


@router.get("/source-health", response_model=list[SourceHealthRead], tags=["sources"])
def source_health(session: Session = Depends(get_db)) -> list[SourceHealthRead]:
    service = SourceService(session)
    return [SourceHealthRead.model_validate(s) for s in service.list_health()]
