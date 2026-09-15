"""Ingestion trigger endpoint — supports both Celery and FastAPI BackgroundTasks execution.

Ensures that whether external Redis/Celery daemons are active or in local dev,
clicking Ingest will reliably fetch feeds, persist articles, run the intelligence
pipeline, and update clustered news events.
"""

from __future__ import annotations

import threading
import uuid
from typing import Set

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.enums import JobStatus
from app.repositories.source_repository import SourceRepository
from app.schemas.ingest import (
    IngestStopRequest,
    IngestStopResponse,
    IngestTriggerRequest,
    IngestTriggerResponse,
)
from app.services.ingestion_service import IngestionService

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_cancellation_events: dict[str, threading.Event] = {}
_active_celery_tasks: dict[str, set[str]] = {}
_cancellation_lock = threading.Lock()


def _register_cancellation_token(token: str) -> threading.Event:
    with _cancellation_lock:
        ev = threading.Event()
        _cancellation_events[token] = ev
        return ev


def _is_cancelled(token: str) -> bool:
    with _cancellation_lock:
        ev = _cancellation_events.get(token)
        if ev and ev.is_set():
            return True
        global_ev = _cancellation_events.get("all")
        if global_ev and global_ev.is_set():
            return True
        return False


def _signal_cancellation(token: str | None = None) -> list[str]:
    cancelled_tokens: list[str] = []
    with _cancellation_lock:
        if token is None or token == "all":
            for t, ev in _cancellation_events.items():
                ev.set()
                cancelled_tokens.append(t)
            if "all" not in _cancellation_events:
                ev = threading.Event()
                ev.set()
                _cancellation_events["all"] = ev
            else:
                _cancellation_events["all"].set()
        else:
            ev = _cancellation_events.get(token)
            if ev:
                ev.set()
            else:
                ev = threading.Event()
                ev.set()
                _cancellation_events[token] = ev
            cancelled_tokens.append(token)
    return cancelled_tokens


def _cleanup_cancellation_token(token: str) -> None:
    with _cancellation_lock:
        _cancellation_events.pop(token, None)
        _active_celery_tasks.pop(token, None)


def _background_run_ingest(source_ids: list[uuid.UUID], cancel_token: str = "all") -> None:
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
            sid_str = str(sid)
            if _is_cancelled(cancel_token) or _is_cancelled(sid_str):
                logger.info("bg_ingest_cancelled_for_source", source_id=sid_str)
                continue

            try:
                res = service.ingest_source(
                    sid,
                    cancel_check=lambda s=sid_str: _is_cancelled(cancel_token) or _is_cancelled(s),
                )
                session.commit()
                if res.status != JobStatus.skipped:
                    created_article_ids.extend(res.created_ids)
            except Exception:
                session.rollback()
                logger.exception("bg_ingest_source_failed", source_id=sid_str)

        if _is_cancelled(cancel_token):
            logger.info("bg_ingest_cancelled_before_intelligence_pipeline")
            return

        article_repo = ArticleRepository(session)
        processable_ids = article_repo.select_processable_ids(limit=10)
        articles_to_process = list(dict.fromkeys(created_article_ids + processable_ids))[:15]

        if not articles_to_process:
            return

        provider = get_text_provider()
        pipeline = IntelligencePipeline(session, provider)
        verification_pipe = VerificationPipeline(session, provider)
        trend_pipe = TrendPipeline(session, provider)
        event_repo = EventRepository(session)

        affected_event_ids: Set[uuid.UUID] = set()
        for art_id in articles_to_process:
            if _is_cancelled(cancel_token):
                logger.info("bg_ingest_cancelled_during_pipeline")
                break
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
            if _is_cancelled(cancel_token):
                logger.info("bg_ingest_cancelled_during_event_scoring")
                break
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
        _cleanup_cancellation_token(cancel_token)


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
        token = str(source.id)
        _register_cancellation_token(token)
        task_id = str(uuid.uuid4())
        background_tasks.add_task(_background_run_ingest, [source.id], cancel_token=token)
        if _is_redis_available():
            try:
                from app.workers.tasks import ingest_source
                celery_task = ingest_source.delay(str(source.id))
                task_id = celery_task.id
                with _cancellation_lock:
                    _active_celery_tasks.setdefault(token, set()).add(task_id)
            except Exception:
                pass

        return IngestTriggerResponse(
            enqueued=True,
            task_id=task_id,
            source_ids=[source.id],
            message=f"Ingestion started for source '{source.slug}'",
        )

    active_ids = repo.list_active_ids()
    token = "all"
    _register_cancellation_token(token)
    for sid in active_ids:
        _register_cancellation_token(str(sid))
    task_id = str(uuid.uuid4())
    background_tasks.add_task(_background_run_ingest, active_ids, cancel_token=token)
    if _is_redis_available():
        try:
            from app.workers.tasks import ingest_all_active
            celery_task = ingest_all_active.delay()
            task_id = celery_task.id
            with _cancellation_lock:
                _active_celery_tasks.setdefault(token, set()).add(task_id)
        except Exception:
            pass

    return IngestTriggerResponse(
        enqueued=True,
        task_id=task_id,
        source_ids=active_ids,
        message=f"Ingestion started for {len(active_ids)} active source(s)",
    )


@router.post("/stop", response_model=IngestStopResponse)
def stop_ingest(
    payload: IngestStopRequest,
    session: Session = Depends(get_db),
) -> IngestStopResponse:
    source_id_str = str(payload.source_id) if payload.source_id else None
    _signal_cancellation(source_id_str)

    # Revoke any tracked Celery tasks if Redis/Celery is active
    if _is_redis_available():
        try:
            from app.workers.celery_app import celery_app
            with _cancellation_lock:
                tasks_to_revoke: set[str] = set()
                if source_id_str:
                    tasks_to_revoke.update(_active_celery_tasks.get(source_id_str, set()))
                else:
                    for task_set in _active_celery_tasks.values():
                        tasks_to_revoke.update(task_set)
                for tid in tasks_to_revoke:
                    celery_app.control.revoke(tid, terminate=True)
        except Exception:
            logger.warning("celery_revoke_failed")

    msg = (
        f"Ingestion stopped for source"
        if source_id_str
        else "All active ingestions stopped"
    )
    logger.info("ingest_stop_requested", source_id=source_id_str)
    return IngestStopResponse(
        stopped=True,
        source_id=payload.source_id,
        message=msg,
    )

