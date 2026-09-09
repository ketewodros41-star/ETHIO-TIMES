"""Celery tasks for ingestion and source health.

Each task manages its own DB session (workers run outside the request/response
lifecycle). The API layer only ever *enqueues* these tasks; it never runs
ingestion synchronously in the request path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.news_source import NewsSource
from app.repositories.source_repository import SourceRepository
from app.services.ingestion_service import IngestionService
from app.workers.celery_app import celery_app

configure_logging()
logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.ingest_source", max_retries=3)
def ingest_source(self, source_id: str) -> dict:
    """Ingest a single source. Idempotent by canonical URL."""
    import uuid

    session = SessionLocal()
    try:
        service = IngestionService(session)
        result = service.ingest_source(uuid.UUID(source_id), celery_task_id=self.request.id)
        session.commit()
        return result.as_dict()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ingest_source_task_error", source_id=source_id)
        raise
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.poll_due_sources")
def poll_due_sources() -> dict:
    """Enqueue ingest tasks for every active source that is due for a crawl."""
    session = SessionLocal()
    try:
        repo = SourceRepository(session)
        due_ids: list[str] = []
        for source in repo.list_active_rss_sources():
            if _is_due(source):
                ingest_source.delay(str(source.id))
                due_ids.append(str(source.id))
        logger.info("poll_due_sources", enqueued=len(due_ids))
        return {"enqueued": len(due_ids), "source_ids": due_ids}
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.ingest_all_active")
def ingest_all_active() -> dict:
    """Enqueue ingest for all active sources regardless of schedule (manual)."""
    session = SessionLocal()
    try:
        repo = SourceRepository(session)
        ids = [str(sid) for sid in repo.list_active_ids()]
        for sid in ids:
            ingest_source.delay(sid)
        return {"enqueued": len(ids), "source_ids": ids}
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.source_health_sweep")
def source_health_sweep() -> dict:
    """Placeholder health sweep: flag sources not checked in a long time.

    Kept intentionally light in Phase 1; richer SLA/alerting is a later phase.
    """
    session = SessionLocal()
    try:
        repo = SourceRepository(session)
        stale = 0
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        for source in repo.list_active_rss_sources():
            if source.last_checked_at and source.last_checked_at < cutoff:
                stale += 1
        logger.info("source_health_sweep", stale=stale)
        return {"stale": stale}
    finally:
        session.close()


def _is_due(source: NewsSource) -> bool:
    if source.last_checked_at is None:
        return True
    elapsed = datetime.now(UTC) - source.last_checked_at
    return elapsed >= timedelta(minutes=source.crawl_frequency_minutes)
