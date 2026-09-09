"""Celery tasks for ingestion and source health.

Each task manages its own DB session (workers run outside the request/response
lifecycle). The API layer only ever *enqueues* these tasks; it never runs
ingestion synchronously in the request path.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.integrations.ai.registry import get_text_provider
from app.models.audit import AuditLog, PipelineJob
from app.models.enums import AuditAction, EventVerifyStatus, JobStatus, ProcessingStatus
from app.models.news_source import NewsSource
from app.repositories.article_repository import ArticleRepository
from app.repositories.event_repository import EventRepository
from app.repositories.source_repository import SourceRepository
from app.services.ingestion_service import IngestionService
from app.services.intelligence.pipeline import IntelligencePipeline
from app.services.intelligence.verification_pipeline import VerificationPipeline
from app.workers.celery_app import celery_app

configure_logging()
logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.ingest_source", max_retries=3)
def ingest_source(self, source_id: str) -> dict:
    """Ingest a single source, then enqueue the intelligence pipeline per new article."""
    session = SessionLocal()
    try:
        service = IngestionService(session)
        result = service.ingest_source(uuid.UUID(source_id), celery_task_id=self.request.id)
        session.commit()
        # Enqueue the intelligence pipeline for each newly-created article.
        for article_id in result.created_ids:
            process_article.delay(str(article_id))
        return result.as_dict()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("ingest_source_task_error", source_id=source_id)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="app.workers.tasks.process_article", max_retries=3)
def process_article(self, article_id: str) -> dict:
    """Run the intelligence pipeline for one article.

    Uses a row-level lock (SKIP LOCKED) so concurrent workers never process the
    same article. Records a PipelineJob and, on dead-letter, an audit entry.
    """
    session = SessionLocal()
    try:
        repo = ArticleRepository(session)
        article = repo.lock_for_processing(uuid.UUID(article_id))
        if article is None:
            # Not found, or currently locked by another worker.
            return {"skipped": True, "article_id": article_id}

        source_id = article.source_id
        pipeline = IntelligencePipeline(session, get_text_provider())
        result = pipeline.process(article)

        job = PipelineJob(
            task_name="process_article",
            celery_task_id=self.request.id,
            source_id=source_id,
            status=JobStatus.success if result.error is None else JobStatus.failed,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            items_processed=1,
            items_created=1 if "cluster" in result.steps_run else 0,
            error_message=result.error,
            detail=result.as_dict(),
        )
        session.add(job)

        if result.final_status == ProcessingStatus.dead_letter:
            session.add(
                AuditLog(
                    action=AuditAction.system,
                    entity_type="article",
                    entity_id=article_id,
                    message="Article moved to dead_letter after repeated failures",
                    changes=result.as_dict(),
                )
            )
        session.commit()
        if result.event_id:
            verify_event.delay(result.event_id)
        return result.as_dict()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("process_article_task_error", article_id=article_id)
        raise
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.poll_pending_articles")
def poll_pending_articles(limit: int = 200) -> dict:
    """Enqueue the pipeline for articles that still need processing.

    When no AI provider is configured, only relevance + analysis (which have
    deterministic fallbacks) can advance, so we do not re-enqueue articles that
    are already ``analyzed`` (they would loop). With a provider, all non-terminal
    states are advanced.
    """
    session = SessionLocal()
    try:
        provider = get_text_provider()
        repo = ArticleRepository(session)
        statuses = (
            None
            if provider.is_available()
            else [ProcessingStatus.pending, ProcessingStatus.failed]
        )
        ids = repo.select_processable_ids(limit=limit, statuses=statuses)
        for article_id in ids:
            process_article.delay(str(article_id))
        logger.info("poll_pending_articles", enqueued=len(ids))
        return {"enqueued": len(ids)}
    finally:
        session.close()


@celery_app.task(bind=True, name="app.workers.tasks.verify_event", max_retries=3)
def verify_event(self, event_id: str) -> dict:
    """Run claim extraction, evidence, contradictions, and scoring for one event.

    Uses a row-level lock (SKIP LOCKED). Records a PipelineJob and, on
    dead-letter, an audit entry. Idempotent: already-verified events with no
    new coverage are skipped.
    """
    session = SessionLocal()
    try:
        repo = EventRepository(session)
        event = repo.lock_for_verification(uuid.UUID(event_id))
        if event is None:
            return {"skipped": True, "event_id": event_id, "reason": "locked_or_missing"}

        pipeline = VerificationPipeline(session, get_text_provider())
        result = pipeline.process(event)

        job = PipelineJob(
            task_name="verify_event",
            celery_task_id=self.request.id,
            event_id=event.id,
            status=JobStatus.success if result.error is None else JobStatus.failed,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            items_processed=1,
            items_created=result.claim_count,
            error_message=result.error,
            detail=result.as_dict(),
        )
        session.add(job)

        if result.final_status == EventVerifyStatus.dead_letter:
            session.add(
                AuditLog(
                    action=AuditAction.system,
                    entity_type="news_event",
                    entity_id=event_id,
                    message="Event verification moved to dead_letter after repeated failures",
                    changes=result.as_dict(),
                )
            )
        session.commit()
        return result.as_dict()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("verify_event_task_error", event_id=event_id)
        raise
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.poll_pending_verifications")
def poll_pending_verifications(limit: int = 100) -> dict:
    """Enqueue verification for clustered events that still need it."""
    session = SessionLocal()
    try:
        repo = EventRepository(session)
        ids = repo.select_pending_verification_ids(limit=limit)
        for event_id in ids:
            verify_event.delay(str(event_id))
        logger.info("poll_pending_verifications", enqueued=len(ids))
        return {"enqueued": len(ids)}
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
