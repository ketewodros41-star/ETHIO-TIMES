"""Ingestion trigger endpoint — supports both Celery and FastAPI BackgroundTasks execution.

Ensures that whether external Redis/Celery daemons are active or in local dev,
clicking Ingest will reliably fetch feeds, persist articles, run the intelligence
pipeline, and update clustered news events.
"""

from __future__ import annotations

import uuid
from typing import Set

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.repositories.source_repository import SourceRepository
from app.schemas.ingest import IngestTriggerRequest, IngestTriggerResponse
from app.services.ingestion_service import IngestionService

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _background_run_ingest(source_ids: list[uuid.UUID]) -> None:
    """Background runner for ingesting sources and processing articles into events."""
    session = SessionLocal()
    try:
        from app.integrations.ai.registry import get_text_provider
        from app.repositories.article_repository import ArticleRepository
        from app.repositories.event_repository import EventRepository
        from app.services.intelligence.pipeline import IntelligencePipeline
        from app.services.intelligence.trend_pipeline import TrendPipeline
        from app.services.intelligence.verification_pipeline import VerificationPipeline

        service = IngestionService(session)
        created_article_ids: list[uuid.UUID] = []

        for sid in source_ids:
            try:
                res = service.ingest_source(sid)
                session.commit()
                created_article_ids.extend(res.created_ids)
            except Exception:
                session.rollback()
                logger.exception("bg_ingest_source_failed", source_id=str(sid))

        article_repo = ArticleRepository(session)
        processable_ids = article_repo.select_processable_ids(limit=100)
        articles_to_process = list(dict.fromkeys(created_article_ids + processable_ids))

        if not articles_to_process:
            return

        provider = get_text_provider()
        pipeline = IntelligencePipeline(session, provider)
        verification_pipe = VerificationPipeline(session, provider)
        trend_pipe = TrendPipeline(session, provider)
        event_repo = EventRepository(session)

        affected_event_ids: Set[uuid.UUID] = set()
        for art_id in articles_to_process:
            article = article_repo.get(art_id)
            if article:
                try:
                    pipe_res = pipeline.process(article)
                    session.commit()
                    if pipe_res.event_id:
                        ev_uuid = (
                            uuid.UUID(pipe_res.event_id)
                            if isinstance(pipe_res.event_id, str)
                            else pipe_res.event_id
                        )
                        affected_event_ids.add(ev_uuid)
                except Exception:
                    session.rollback()
                    logger.exception("bg_pipeline_process_failed", article_id=str(art_id))

        for ev_id in affected_event_ids:
            try:
                ev = event_repo.get(ev_id)
                if ev:
                    verification_pipe.process(ev)
                    trend_pipe.process(ev)
                    session.commit()
            except Exception:
                session.rollback()
                logger.exception("bg_event_scoring_failed", event_id=str(ev_id))

    except Exception:
        logger.exception("bg_ingest_orchestration_failed")
    finally:
        session.close()


def _is_redis_available() -> bool:
    try:
        import socket
        with socket.socket() as s:
            s.settimeout(0.15)
            return s.connect_ex(("localhost", 6379)) == 0
    except Exception:
        return False


@router.post("/trigger", response_model=IngestTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_ingest(
    payload: IngestTriggerRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> IngestTriggerResponse:
    repo = SourceRepository(session)

    if payload.source_id is not None:
        source = repo.get(payload.source_id)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
            )
        task_id = str(uuid.uuid4())
        background_tasks.add_task(_background_run_ingest, [source.id])
        if _is_redis_available():
            try:
                from app.workers.tasks import ingest_source
                celery_task = ingest_source.delay(str(source.id))
                task_id = celery_task.id
            except Exception:
                pass

        return IngestTriggerResponse(
            enqueued=True,
            task_id=task_id,
            source_ids=[source.id],
            message=f"Ingestion started for source '{source.slug}'",
        )

    active_ids = repo.list_active_ids()
    task_id = str(uuid.uuid4())
    background_tasks.add_task(_background_run_ingest, active_ids)
    if _is_redis_available():
        try:
            from app.workers.tasks import ingest_all_active
            celery_task = ingest_all_active.delay()
            task_id = celery_task.id
        except Exception:
            pass

    return IngestTriggerResponse(
        enqueued=True,
        task_id=task_id,
        source_ids=active_ids,
        message=f"Ingestion started for {len(active_ids)} active source(s)",
    )

