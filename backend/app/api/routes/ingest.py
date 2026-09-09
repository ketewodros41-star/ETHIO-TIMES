"""Ingestion trigger endpoint — ENQUEUE ONLY.

This never runs ingestion synchronously. It validates the requested source(s)
and enqueues Celery tasks, returning immediately. If the broker is unreachable,
it returns a clear error rather than blocking the request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.repositories.source_repository import SourceRepository
from app.schemas.ingest import IngestTriggerRequest, IngestTriggerResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/trigger", response_model=IngestTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_ingest(
    payload: IngestTriggerRequest, session: Session = Depends(get_db)
) -> IngestTriggerResponse:
    # Import here to avoid importing Celery/Redis at app import time.
    from app.workers.tasks import ingest_all_active, ingest_source

    repo = SourceRepository(session)

    if payload.source_id is not None:
        source = repo.get(payload.source_id)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
            )
        try:
            task = ingest_source.delay(str(source.id))
        except Exception as exc:  # noqa: BLE001 - broker unreachable
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not enqueue task (broker unavailable): {exc}",
            ) from exc
        return IngestTriggerResponse(
            enqueued=True,
            task_id=task.id,
            source_ids=[source.id],
            message=f"Enqueued ingest for source '{source.slug}'",
        )

    # No specific source => enqueue all active sources.
    active_ids = repo.list_active_ids()
    try:
        task = ingest_all_active.delay()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not enqueue task (broker unavailable): {exc}",
        ) from exc
    return IngestTriggerResponse(
        enqueued=True,
        task_id=task.id,
        source_ids=active_ids,
        message=f"Enqueued ingest for {len(active_ids)} active source(s)",
    )
