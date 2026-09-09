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
from app.services.intelligence.trend_pipeline import TrendPipeline
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
            score_event_trend.delay(result.event_id)
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
        if result.error is None:
            score_event_trend.delay(event_id)
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


@celery_app.task(bind=True, name="app.workers.tasks.score_event_trend", max_retries=3)
def score_event_trend(self, event_id: str) -> dict:
    """Recompute velocity + weighted trend score for one event.

    Uses a row-level lock (SKIP LOCKED). Records a PipelineJob. Idempotent: a
    freshly scored event with no new coverage is skipped.
    """
    session = SessionLocal()
    try:
        repo = EventRepository(session)
        event = repo.lock_for_trend(uuid.UUID(event_id))
        if event is None:
            return {"skipped": True, "event_id": event_id, "reason": "locked_or_missing"}

        pipeline = TrendPipeline(session, get_text_provider())
        result = pipeline.process(event)

        job = PipelineJob(
            task_name="score_event_trend",
            celery_task_id=self.request.id,
            event_id=event.id,
            status=JobStatus.success if result.error is None else JobStatus.failed,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            items_processed=1,
            items_created=0,
            error_message=result.error,
            detail=result.as_dict(),
        )
        session.add(job)
        session.commit()
        return result.as_dict()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("score_event_trend_task_error", event_id=event_id)
        raise
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.poll_stale_trends")
def poll_stale_trends(limit: int = 100) -> dict:
    """Enqueue trend rescoring for events that are stale or have new coverage."""
    session = SessionLocal()
    try:
        repo = EventRepository(session)
        ids = repo.select_stale_trend_ids(limit=limit)
        for eid in ids:
            score_event_trend.delay(str(eid))
        logger.info("poll_stale_trends", enqueued=len(ids))
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


@celery_app.task(bind=True, name="app.workers.tasks.generate_visual_asset", max_retries=2)
def generate_visual_asset(self, event_id: str) -> dict:
    """Run Visual Director → Prompt Engine → Gemini image gen → ImageCritic."""
    session = SessionLocal()
    try:
        repo = EventRepository(session)
        event = repo.get(uuid.UUID(event_id))
        if event is None:
            return {"skipped": True, "reason": "event_not_found"}

        from app.integrations.ai.registry import get_image_provider, get_text_provider
        from app.services.social.editorial_engine import EditorialEngine
        from app.services.social.image_pipeline import ImagePipeline

        text_provider = get_text_provider()
        image_provider = get_image_provider()
        editorial = EditorialEngine(text_provider)
        brief = editorial.compose(event)
        pipeline = ImagePipeline(session, text_provider, image_provider)
        result = pipeline.run(event, brief)
        session.commit()
        return {
            "selected_asset_id": str(result.selected_asset.id) if result.selected_asset else None,
            "attempts": result.attempts,
        }
    except Exception:
        session.rollback()
        logger.exception("generate_visual_asset_error", event_id=event_id)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="app.workers.tasks.compose_post", max_retries=2)
def compose_post(self, event_id: str, format: str = "portrait", theme: str | None = None) -> dict:
    """EditorialEngine → CaptionBuilder → save SocialPost(status=draft)."""
    session = SessionLocal()
    try:
        from app.integrations.ai.registry import get_text_provider
        from app.models.enums import InstagramPostFormat
        from app.models.social_post import SocialPost
        from app.repositories.social_post_repository import SocialPostRepository
        from app.repositories.visual_asset_repository import VisualAssetRepository
        from app.services.social.caption_builder import CaptionBuilder
        from app.services.social.editorial_engine import EditorialEngine

        repo = EventRepository(session)
        event = repo.get_detail_for_compose(uuid.UUID(event_id))
        if event is None:
            return {"skipped": True, "reason": "event_not_found"}

        provider = get_text_provider()
        engine = EditorialEngine(provider)
        brief = engine.compose(event)
        builder = CaptionBuilder()
        caption = builder.build(brief)

        fmt = (
            InstagramPostFormat(format)
            if format in [f.value for f in InstagramPostFormat]
            else InstagramPostFormat.portrait
        )
        selected_theme = theme or brief.suggested_theme
        asset_repo = VisualAssetRepository(session)
        selected_asset = asset_repo.get_selected_for_event(uuid.UUID(event_id))

        snapshot = {
            "auto_publish_eligible": event.auto_publish_eligible,
            "review_required": event.review_required,
            "verification_score": event.verification_score,
            "trend_score": getattr(event, "trend_score", 0),
            "event_verification_status": (
                event.event_verification_status.value
                if hasattr(event.event_verification_status, "value")
                else str(event.event_verification_status)
            ),
            "carousel_slides": brief.carousel_slides,
        }

        post = SocialPost(
            event_id=event.id,
            visual_asset_id=selected_asset.id if selected_asset else None,
            format=fmt,
            theme=selected_theme,
            headline=brief.headline,
            caption=caption,
            hashtags=brief.hashtags,
            source_attribution=brief.source_attribution,
            key_facts=brief.key_facts,
            eligibility_snapshot=snapshot,
        )
        post_repo = SocialPostRepository(session)
        post_repo.create(post)
        session.commit()
        return {"post_id": str(post.id), "theme": selected_theme, "format": fmt.value}
    except Exception:
        session.rollback()
        logger.exception("compose_post_task_error", event_id=event_id)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="app.workers.tasks.render_post", max_retries=2)
def render_post(self, post_id: str) -> dict:
    """RenderService → update status=rendered."""
    session = SessionLocal()
    try:
        from app.models.enums import SocialPostStatus
        from app.models.social_post import SocialPost
        from app.repositories.social_post_repository import SocialPostRepository
        from app.services.social.render_service import RenderError, RenderService

        post = session.get(SocialPost, uuid.UUID(post_id))
        if post is None:
            return {"skipped": True, "reason": "post_not_found"}

        render_svc = RenderService()
        try:
            path = render_svc.render_post(post)
            repo = SocialPostRepository(session)
            repo.update_media(post.id, str(path), None)
            repo.update_status(post.id, SocialPostStatus.rendered)
            session.commit()
            return {"post_id": post_id, "media_path": str(path)}
        except RenderError as exc:
            repo = SocialPostRepository(session)
            repo.update_status(post.id, SocialPostStatus.failed, error=str(exc))
            session.commit()
            return {"post_id": post_id, "error": str(exc)}
    except Exception:
        session.rollback()
        logger.exception("render_post_task_error", post_id=post_id)
        raise
    finally:
        session.close()


@celery_app.task(bind=True, name="app.workers.tasks.publish_post", max_retries=3)
def publish_post(self, post_id: str) -> dict:
    """PublishService → gate → InstagramPublisher → status=published or failed."""
    session = SessionLocal()
    try:
        from app.integrations.publishers.instagram import InstagramPublisher
        from app.models.enums import SocialPostStatus
        from app.models.social_post import SocialPost
        from app.repositories.social_post_repository import SocialPostRepository
        from app.services.social.publish_service import PublishBlockedError, PublishService
        from app.services.social.render_service import RenderService

        post = session.get(SocialPost, uuid.UUID(post_id))
        if post is None:
            return {"skipped": True, "reason": "post_not_found"}

        publisher = InstagramPublisher()
        render_svc = RenderService()
        svc = PublishService(session, publisher, render_svc)
        try:
            result = svc.publish(post)
            session.commit()
            return {
                "post_id": post_id,
                "ig_post_id": result.platform_post_id,
                "dry_run": result.dry_run,
            }
        except PublishBlockedError as exc:
            repo = SocialPostRepository(session)
            repo.update_status(post.id, SocialPostStatus.failed, error=str(exc))
            session.commit()
            return {"post_id": post_id, "blocked": True, "reason": exc.reason}
    except Exception:
        session.rollback()
        logger.exception("publish_post_task_error", post_id=post_id)
        raise
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.auto_compose_eligible_events")
def auto_compose_eligible_events(limit: int = 20) -> dict:
    """Beat: find trending/breaking events with auto_publish_eligible=True
    and no existing SocialPost → enqueue compose_post.
    """
    session = SessionLocal()
    try:
        from sqlalchemy import select
        from app.models.enums import TrendStatus
        from app.models.news_event import NewsEvent
        from app.repositories.social_post_repository import SocialPostRepository

        post_repo = SocialPostRepository(session)
        stmt = (
            select(NewsEvent)
            .where(
                NewsEvent.auto_publish_eligible.is_(True),
                NewsEvent.review_required.is_(False),
                NewsEvent.trend_status.in_(
                    [TrendStatus.trending, TrendStatus.high_priority, TrendStatus.breaking]
                ),
            )
            .limit(limit)
        )
        events = list(session.scalars(stmt).all())
        enqueued = []
        for event in events:
            if not post_repo.has_post_for_event(event.id):
                compose_post.delay(str(event.id))
                enqueued.append(str(event.id))
        logger.info("auto_compose_eligible_events", enqueued=len(enqueued))
        return {"enqueued": len(enqueued)}
    finally:
        session.close()
