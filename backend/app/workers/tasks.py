"""Celery tasks for ingestion and source health.

Each task manages its own DB session (workers run outside the request/response
lifecycle). The API layer only ever *enqueues* these tasks; it never runs
ingestion synchronously in the request path.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.integrations.ai.registry import (
    get_image_provider,
    get_text_provider,
    get_translation_provider,
)
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


def _telegram_slot(
    policy,
    ordinal: int,
    now: datetime,
    used_hours: set[int] | None = None,
) -> datetime:
    """Return today's next configured Addis-time slot, avoiding collisions if used_hours is given."""
    zone = ZoneInfo(policy.timezone)
    local_now = now.astimezone(zone)
    hours = sorted(policy.posting_hours or [8, 11, 14, 17, 20])
    if not hours:
        hours = [8, 11, 14, 17, 20]

    if used_hours is not None:
        occupied = set(used_hours)
        for h in hours:
            if h in occupied:
                continue
            candidate = local_now.replace(hour=h, minute=0, second=0, microsecond=0)
            if candidate > local_now + timedelta(minutes=3):
                return candidate.astimezone(UTC)

        tomorrow = local_now + timedelta(days=1)
        tomorrow_hour = hours[0]
        for h in hours:
            if h not in occupied:
                tomorrow_hour = h
                break
        return tomorrow.replace(hour=tomorrow_hour, minute=0, second=0, microsecond=0).astimezone(UTC)

    if ordinal < len(hours):
        hour = hours[ordinal]
        candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    else:
        last_hour = hours[-1]
        extra_index = ordinal - len(hours) + 1
        candidate = local_now.replace(hour=last_hour, minute=0, second=0, microsecond=0) + timedelta(minutes=30 * extra_index)

    if candidate <= local_now:
        return (now + timedelta(minutes=15 * ordinal)).astimezone(UTC)
    return candidate.astimezone(UTC)


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


@celery_app.task(name="app.workers.tasks.generate_visual_asset_real_photo", max_retries=2, bind=True)
def generate_visual_asset_real_photo(self, event_id: str) -> dict:
    """Try to use real article photo; fall back to AI generation."""
    from app.integrations.ai.registry import get_text_provider, get_image_provider
    from app.repositories.event_repository import EventRepository
    from app.services.social.editorial_engine import EditorialEngine
    from app.services.social.image_pipeline import ImagePipeline

    with SessionLocal() as session:
        event_repo = EventRepository(session)
        event = event_repo.get_with_articles(event_id)
        if event is None:
            return {"error": "event_not_found"}

        pipeline = ImagePipeline(
            session=session,
            text_provider=get_text_provider(),
            image_provider=get_image_provider(),
        )
        result = pipeline.run_real_photo(event)
        session.commit()
        return {
            "asset_id": str(result.selected_asset.id) if result.selected_asset else None,
            "source": "real_photo",
        }


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
            media_url = f"/api/v1/posts/{post.id}/image"
            repo.update_media(post.id, str(path), media_url)
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


# ---------------------------------------------------------------------------
# Bilingual (Amharic & English) advertorial and sponsored content filter.
# Normalizes punctuation (Ethiopic ፡, ።, ፣, etc.), zero-width characters,
# Fidel character variations, and word boundaries.
# ---------------------------------------------------------------------------

_ETHIOPIC_PUNCT_RE = re.compile(r"[\u1360-\u1368\.,;:!\?\"\'\(\)\[\]\{\}\<\>«»/\\_\-–—~|#%&*+=^`@]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\ufeff\u00ad]")
_AMHARIC_CHAR_MAP = {
    # ሠ -> ሰ
    "ሠ": "ሰ", "ሡ": "ሱ", "ሢ": "ሲ", "ሣ": "ሳ", "ሤ": "ሴ", "ሥ": "ስ", "ሦ": "ሶ", "ሧ": "ሷ",
    # ሐ, ኀ -> ሀ
    "ሐ": "ሀ", "ሑ": "ሁ", "ሒ": "ሂ", "ሓ": "ሃ", "ሔ": "ሄ", "ሕ": "ህ", "ሖ": "ሆ",
    "ኀ": "ሀ", "ኁ": "ሁ", "ኂ": "ሂ", "ኃ": "ሃ", "ኄ": "ሄ", "ኅ": "ህ", "ኆ": "ሆ",
    # ዐ -> አ
    "ዐ": "አ", "ዑ": "ኡ", "ዒ": "ኢ", "ዓ": "ኣ", "ዔ": "ኤ", "ዕ": "እ", "ዖ": "ኦ",
    # ፀ -> ጸ
    "ፀ": "ጸ", "ፁ": "ጹ", "ፂ": "ጺ", "ፃ": "ጻ", "ፄ": "ጼ", "ፅ": "ጽ", "ፆ": "ጾ",
}
_AMHARIC_TRANS = str.maketrans(_AMHARIC_CHAR_MAP)


def normalize_filter_text(text: str) -> str:
    """Normalize text for advertorial/content filtering.

    Handles Amharic & Latin punctuation (፣, ።, ፡, etc.), zero-width spaces,
    Fidel character variants (e.g. ሠ->ሰ, ሐ/ኀ->ሀ, ዐ->አ, ፀ->ጸ), and whitespace.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _ETHIOPIC_PUNCT_RE.sub(" ", text)
    text = text.translate(_AMHARIC_TRANS)
    return " ".join(text.lower().split())


_GLOBAL_SPONSOR_SIGNALS: tuple[str, ...] = (
    # English advertorial signals
    "sponsored", "sponsered",            # typo variant
    "advertisement", "advertorial",
    "partner content", "partnered content",
    "ad feature", "promoted content", "paid content",
    "press release", "pr news", "brand story",
    "brought to you by", "in association with",
    "commercial feature", "native ad",
    "ethio telecom", "ethiotelecom",
    "telebirr",

    # Amharic advertorial keywords & variations
    "ማስታወቂያ",                 # advertisement / ad
    "የማስታወቂያ",               # ad prefix
    "ማስተዋወቂያ",               # promotion / promotional
    "የማስተዋወቂያ",             # promotion prefix
    "ስፖንሰር",                   # sponsor
    "የስፖንሰር",                 # sponsored
    "ስፖንሰር የተደረገ",           # sponsored content
    "ስፖንሰር የተደረገ ይዘት",      # sponsored content
    "የስፖንሰር ይዘት",             # sponsored content
    "የተከፈለበት ይዘት",          # paid content
    "የተከፈለበት",               # paid content / paid for
    "የሚከፈልበት ይዘት",          # paid content variation
    "የንግድ ማስታወቂያ",          # commercial advertisement
    "ንግድ ማስታወቂያ",            # commercial advertisement
    "የጋዜጣዊ መግለጫ",           # press release
    "ጋዜጣዊ መግለጫ",            # press release
    "የጋዜጣ መግለጫ",             # press release variation
    "ጋዜጣ መግለጫ",              # press release variation
    "አጋር ይዘት",                 # partner content
    "የአጋር ይዘት",               # partner content
    "ኢትዮ ቴሌኮም",               # Ethio Telecom
    "ኢትዮቴሌኮም",                 # Ethio Telecom (no space)
    "የኢትዮ ቴሌኮም",             # Ethio Telecom prefix
    "የኢትዮቴሌኮም",               # Ethio Telecom prefix
    "ቴሌብር",                    # telebirr
    "ቴሌ ብር",                   # telebirr (with space)
    "የቴሌብር",                  # telebirr prefix
    "ልዩ ቅናሽ",                 # special discount / promotional offer
    "ልዩ ቅናሾች",               # special discounts
    "የማስተዋወቅ",               # promotional
    "የፕሮሞሽን",                 # promotional
    "ፕሮሞሽን",                  # promotion
)

_NORMALIZED_GLOBAL_SPONSOR_SIGNALS: tuple[str, ...] = tuple(
    dict.fromkeys(normalize_filter_text(s) for s in _GLOBAL_SPONSOR_SIGNALS if normalize_filter_text(s))
)


def _is_sponsored_event(event: Any) -> bool:
    """Return True if the event looks like sponsored/advertorial content."""
    title = getattr(event, "title", "") or ""
    summary = getattr(event, "summary", "") or ""
    haystack = normalize_filter_text(f"{title} {summary}")
    for signal in _NORMALIZED_GLOBAL_SPONSOR_SIGNALS:
        if signal in haystack:
            logger.info(
                "sponsored_content_filtered",
                event_id=str(getattr(event, "id", "")),
                matched_signal=signal,
                title=title[:120],
            )
            return True
    return False


_BEAT_SYNONYMS: dict[str, list[str]] = {
    "politics": [
        "politics", "governance", "election", "elections", "parliament", "political", "government", "policy", "diplomacy",
        "minister", "ministry", "prime minister", "president", "cabinet", "legislation", "senate", "congress", "treaty",
        "ፖለቲካ", "መንግስት", "ፓርላማ", "ምርጫ", "ሚኒስትር", "ሚኒስቴር", "ጠቅላይ ሚኒስትር", "ፕሬዝዳንት", "ፖሊሲ", "ዲፕሎማሲ", "ህግ", "ካቢኔ", "አስተዳደር",
    ],
    "business": [
        "business", "economy", "finance", "banking", "market", "trade", "investment", "economic", "stocks", "investor",
        "inflation", "currency", "forex", "birr", "revenue", "export", "import", "commercial", "central bank", "cbe",
        "ቢዝነስ", "ኢኮኖሚ", "ንግድ", "ባንክ", "ፋይናንስ", "ገንዘብ", "ኢንቨስትመንት", "ብር", "ግብር", "ገበያ", "ዋጋ ግሽበት", "ወጪ", "ገቢ",
    ],
    "economy": [
        "economy", "business", "finance", "banking", "market", "trade", "investment", "economic", "stocks", "inflation",
        "ቢዝነስ", "ኢኮኖሚ", "ንግድ", "ባንክ", "ፋይናንስ", "ገንዘብ", "ኢንቨስትመንት", "ብር", "ግብር", "ገበያ",
    ],
    "sports": [
        "sports", "sport", "football", "soccer", "athletics", "olympic", "olympics", "marathon", "premier league", "champions league",
        "la liga", "serie a", "bundesliga", "fifa", "uefa", "caf", "afcon", "world cup", "arsenal", "manchester", "chelsea",
        "liverpool", "man city", "man utd", "tottenham", "barcelona", "real madrid", "bayern", "juventus", "psg", "haaland",
        "messi", "ronaldo", "goal", "match", "penalty", "referee", "transfer", "striker", "coach", "manager", "tournament",
        "ስፖርት", "እግር ኳስ", "እግርኳስ", "ኳስ", "ዋንጫ", "ጨዋታ", "ክለብ", "ግብ", "አርሰናል", "ማንቸስተር", "ቼልሲ", "ሊቨርፑል", "ማን ሲቲ",
        "ፕሪሚየር ሊግ", "ሻምፒዮንስ ሊግ", "አትሌቲክስ", "ማራቶን", "ኦሊምፒክ", "ደርቢ",
    ],
    "football": [
        "football", "soccer", "premier league", "champions league", "sports", "sport", "la liga", "serie a", "bundesliga",
        "fifa", "uefa", "caf", "afcon", "world cup", "arsenal", "manchester", "chelsea", "liverpool", "man city", "man utd",
        "tottenham", "barcelona", "real madrid", "bayern", "juventus", "psg", "haaland", "messi", "ronaldo", "goal", "match",
        "penalty", "referee", "transfer", "striker", "coach", "manager",
        "እግር ኳስ", "እግርኳስ", "ኳስ", "ዋንጫ", "ጨዋታ", "ክለብ", "ግብ", "አርሰናል", "ማንቸስተር", "ቼልሲ", "ሊቨርፑል", "ማን ሲቲ", "ስፖርት",
    ],
    "technology": [
        "technology", "tech", "telecom", "innovation", "digital", "ai", "software", "cyber", "internet", "startup", "data", "cloud",
        "hardware", "artificial intelligence", "app",
        "ቴክኖሎጂ", "ቴሌኮም", "ዲጂታል", "ሰው ሰራሽ አስተዋይ", "ኢንተርኔት",
    ],
    "culture": [
        "culture", "society", "art", "heritage", "entertainment", "music", "diaspora", "community", "tradition", "festival", "holiday", "film",
        "ባህል", "ማህበራዊ", "ኪነ ጥበብ", "ሙዚቃ", "በዓል", "ዳያስፖራ", "ማህበረሰብ", "ቅርስ",
    ],
    "society": [
        "society", "culture", "community", "social", "public", "heritage", "diaspora",
        "ማህበራዊ", "ባህል", "ማህበረሰብ", "ህዝብ",
    ],
    "conflict": [
        "conflict", "security", "military", "defense", "clash", "fano", "tplf", "ola", "war", "peace", "ceasefire", "fighting", "attack", "army", "soldier", "troops",
        "ግጭት", "ፀጥታ", "ጦርነት", "ሰላም", "መከላከያ", "ወታደር", "ሰራዊት", "ጥቃት", "ተኩስ አቁም", "ፋኖ", "ህወሃት",
    ],
    "world affairs": [
        "world", "international", "diplomacy", "global", "foreign", "un", "geopolitics", "summit", "embassy", "ambassador", "bilateral", "nato", "security council",
        "ዓለም አቀፍ", "ዲፕሎማሲ", "የተባበሩት መንግስታት", "ኤምባሲ", "አምባሳደር", "የውጭ ጉዳይ",
    ],
    "world": [
        "world", "international", "diplomacy", "global", "foreign", "un", "geopolitics", "summit", "embassy", "ambassador",
        "ዓለም አቀፍ", "ዲፕሎማሲ", "የተባበሩት መንግስታት", "የውጭ ጉዳይ",
    ],
    "crime": [
        "crime", "police", "investigation", "court", "arrest", "justice", "trial", "prison", "suspect", "charge", "fraud", "theft",
        "ወንጀል", "ፖሊስ", "ምርመራ", "ፍርድ ቤት", "እስር", "ፍትህ", "ተጠርጣሪ",
    ],
    "science": [
        "science", "research", "health", "medicine", "climate", "space", "scientific", "laboratory",
        "ሳይንስ", "ምርምር", "ህክምና",
    ],
    "health": [
        "health", "medical", "hospital", "disease", "vaccine", "who", "doctor", "epidemic", "clinic",
        "ጤና", "ህክምና", "ሆስፒታል", "በሽታ", "ክትባት",
    ],
    "entertainment": [
        "entertainment", "celebrity", "film", "movie", "music", "art", "culture", "cinema", "concert",
        "መዝናኛ", "ሙዚቃ", "ፊልም", "ሲኒማ", "ኪነ ጥበብ",
    ],
    "education": [
        "education", "university", "school", "students", "academic", "college", "scholarship",
        "ትምህርት", "ዩኒቨርሲቲ", "ትምህርት ቤት", "ተማሪዎች",
    ],
    "environment": [
        "environment", "climate", "weather", "green", "drought", "flood", "ecology", "nature",
        "አካባቢ", "አየር ንብረት", "ድርቅ", "ጎርፍ", "ተፈጥሮ",
    ],
    "breaking": [
        "breaking", "urgent", "accident", "incident", "alert", "emergency", "crash", "disaster",
        "ሰበር", "አስቸኳይ", "አደጋ", "ድንገተኛ",
    ],
}


def _event_matches_category(event: Any, cat_term: str, haystack: str) -> bool:
    """Check if an event matches a category term via primary_category, categories list, or synonyms."""
    clean = cat_term.strip().lower()
    synonyms = _BEAT_SYNONYMS.get(clean, [clean])

    primary_cat = (getattr(event, "primary_category", "") or "").lower()
    event_cats = [str(c).lower() for c in (getattr(event, "categories", []) or [])]
    all_cats = [primary_cat] + event_cats

    for syn in synonyms:
        # Check in categories
        if any(syn in c for c in all_cats if c):
            return True
        # Check in title/summary
        if len(syn) <= 3:
            if re.search(r"\b" + re.escape(syn) + r"\b", haystack, re.IGNORECASE):
                return True
        else:
            if syn in haystack:
                return True
    return False


def _passes_bucket_filters(event: Any, bucket_cfg: dict) -> bool:
    """Return True if the event passes the per-bucket content_filters rules."""
    if not bucket_cfg:
        return True

    title = getattr(event, "title", "") or ""
    summary = getattr(event, "summary", "") or ""
    primary_cat = (getattr(event, "primary_category", "") or "").lower()
    haystack = normalize_filter_text(f"{title} {summary}")

    allowed_cats: list[str] = [c.lower() for c in bucket_cfg.get("allowed_categories", [])]
    blocked_cats: list[str] = [c.lower() for c in bucket_cfg.get("blocked_categories", [])]
    allowed_kws: list[str] = [normalize_filter_text(k) for k in bucket_cfg.get("allowed_keywords", []) if k]
    blocked_kws: list[str] = [normalize_filter_text(k) for k in bucket_cfg.get("blocked_keywords", []) if k]

    # Blocked keywords override everything
    for kw in blocked_kws:
        if kw and kw in haystack:
            logger.info("content_filter_blocked_keyword", event_id=str(getattr(event, "id", "")), keyword=kw)
            return False

    # Blocked categories
    if blocked_cats:
        for bc in blocked_cats:
            if _event_matches_category(event, bc, haystack):
                logger.info("content_filter_blocked_category", event_id=str(getattr(event, "id", "")), category=bc)
                return False

    # Allowed categories (whitelist; empty = allow all)
    if allowed_cats:
        if not any(_event_matches_category(event, ac, haystack) for ac in allowed_cats):
            logger.info("content_filter_allowed_cat_miss", event_id=str(getattr(event, "id", "")), category=primary_cat)
            return False

    # Allowed keywords (whitelist; empty = allow all)
    if allowed_kws and not any(kw in haystack for kw in allowed_kws):
        logger.info("content_filter_allowed_kw_miss", event_id=str(getattr(event, "id", "")))
        return False

    return True


@celery_app.task(name="app.workers.tasks.plan_telegram_posts")
def plan_telegram_posts() -> dict:
    """Plan quota-bound Telegram posts; never sends a message itself."""
    from sqlalchemy import and_, func, not_, or_, select
    from app.models.news_event import NewsEvent
    from app.models.telegram_post import TelegramPost, TelegramPublishingSettings
    from app.schemas.social_post import EditorialTranslationRequest
    from app.services.social.image_pipeline import ImagePipeline
    from app.services.social.translation_service import (
        EditorialTranslationService,
        TranslationUnavailableError,
        _amharic_enough,
    )

    session = SessionLocal()
    candidates_by_bucket: dict[str, list[NewsEvent]] = {}
    try:
        policy = session.get(TelegramPublishingSettings, 1)
        if policy is None or not policy.enabled:
            return {"planned": 0, "reason": "telegram_automation_disabled"}

        # -----------------------------------------------------------------------
        # Problem 1 — Self-healing dry_run check.
        # If enabled=True but dry_run=True, log a CRITICAL alert and auto-reset
        # to prevent silent test pollution freezing live publishing.
        # -----------------------------------------------------------------------
        if policy.enabled and policy.dry_run:
            logger.critical(
                "dry_run_self_heal_triggered",
                message="Telegram automation is ENABLED but dry_run=True. "
                        "This usually means test pollution. Automatically resetting dry_run=False.",
            )
            try:
                policy.dry_run = False
                session.commit()
                session.refresh(policy)
                logger.info("dry_run_self_heal_success")
            except Exception:
                session.rollback()
                logger.exception("dry_run_self_heal_failed")
                # Continue with the current (True) value rather than aborting the task

        now = datetime.now(UTC)
        zone = ZoneInfo(policy.timezone)
        local_now = now.astimezone(zone)
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        day_end = (local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(UTC)
        today_posts = list(session.scalars(select(TelegramPost).where(
            TelegramPost.scheduled_at >= day_start, TelegramPost.scheduled_at < day_end,
            TelegramPost.status.in_(["scheduled", "publishing", "simulated", "published"]),
        )).all())

        def _is_test_post(p: TelegramPost) -> bool:
            if p.telegram_message_id and p.telegram_message_id.startswith("msg-"):
                return True
            if isinstance(p.policy_snapshot, dict) and p.policy_snapshot.get("test_dispatch"):
                return True
            if p.content_bucket and p.content_bucket.startswith("test_"):
                return True
            return False

        if not policy.dry_run:
            # When in live publishing mode, simulated dry-run posts and test dispatches
            # must not count against the real daily quota.
            counted_posts = [
                p for p in today_posts
                if p.status != "simulated"
                and not p.dry_run
                and not (p.telegram_message_id and p.telegram_message_id.startswith("dry-run-"))
                and not _is_test_post(p)
            ]
            already_event_ids = set(session.scalars(
                select(TelegramPost.event_id).where(
                    TelegramPost.status.in_(["scheduled", "publishing", "published"]),
                    TelegramPost.dry_run.is_(False),
                    or_(
                        TelegramPost.telegram_message_id.is_(None),
                        and_(
                            ~TelegramPost.telegram_message_id.ilike("msg-%"),
                            ~TelegramPost.telegram_message_id.ilike("dry-run-%"),
                        ),
                    ),
                )
            ).all())
        else:
            counted_posts = [
                p for p in today_posts
                if not _is_test_post(p)
            ]
            already_event_ids = set(session.scalars(
                select(TelegramPost.event_id).where(
                    TelegramPost.status.in_(["scheduled", "publishing", "simulated", "published"]),
                    or_(
                        TelegramPost.telegram_message_id.is_(None),
                        ~TelegramPost.telegram_message_id.ilike("msg-%"),
                    ),
                )
            ).all())

        existing_by_bucket = {
            bucket: sum(post.content_bucket == bucket for post in counted_posts)
            for bucket in ("ethiopia", "international")
        }
        scheduled_hours_today: set[int] = {
            p.scheduled_at.astimezone(zone).hour
            for p in counted_posts
            if p.scheduled_at and p.scheduled_at.astimezone(zone).date() == local_now.date()
        }

        # Per-bucket filter config from the policy (Problem 3)
        raw_content_filters: dict = {}
        if hasattr(policy, "content_filters") and isinstance(policy.content_filters, dict):
            raw_content_filters = policy.content_filters

        # Comprehensive Ethiopian regional indicators
        ethiopia_region_terms = (
            "ethiop", "addis", "amhara", "tigray", "oromia", "somali", "afar",
            "benishangul", "gambella", "harar", "sidama", "dire dawa",
            "southern nations", "south west", "raya", "wollega", "axum", "mekelle"
        )
        eth_region_cond = or_(*(NewsEvent.primary_region.ilike(f"%{t}%") for t in ethiopia_region_terms))
        eth_title_cond = or_(*(NewsEvent.title.ilike(f"%{t}%") for t in ("%ethiop%", "%addis%", "%amhara%", "%tigray%", "%oromia%")))
        is_ethiopia_expr = or_(eth_region_cond, eth_title_cond)

        # Refined International Expression: Must NOT be Ethiopian, AND must meet positive relevance signals
        intl_category_cond = NewsEvent.primary_category.in_([
            "World", "World News", "International News", "International Relations", "world", "world news", "Diplomacy", "diplomacy",
            "Sports", "sports", "football", "Football", "Business", "business", "Technology", "technology", "Politics", "politics", "Science", "science"
        ])
        intl_priority_regions = (
            "africa", "horn of africa", "red sea", "nile", "sudan", "somalia", "somaliland",
            "kenya", "eritrea", "djibouti", "egypt", "middle east", "united nations",
            "united states", "china", "russia", "europe", "g7", "g20", "african union",
            "world bank", "imf", "saudi", "uae", "yemen"
        )
        intl_region_cond = or_(*(NewsEvent.primary_region.ilike(f"%{r}%") for r in intl_priority_regions))
        intl_title_cond = or_(*(NewsEvent.title.ilike(f"%{r}%") for r in intl_priority_regions))
        intl_origin_cond = or_(
            func.lower(NewsEvent.primary_region) == "international",
            NewsEvent.primary_region.ilike("%international%"),
            NewsEvent.primary_region.ilike("%global%"),
        )
        intl_quality_signal = or_(
            intl_region_cond,
            intl_title_cond,
            intl_category_cond,
            intl_origin_cond,
            NewsEvent.significance_score >= 0.5,
            NewsEvent.article_count >= 2,
        )
        is_intl_expr = and_(
            not_(eth_region_cond),
            not_(eth_title_cond),
            intl_quality_signal,
        )

        freshness_h = getattr(policy, "freshness_hours", 36) or 36
        bypass_breaking = getattr(policy, "bypass_freshness_for_breaking", True)
        freshness_tiers = [freshness_h, 72, 168]

        for bucket, quota in (
            ("ethiopia", policy.ethiopia_posts_per_day),
            ("international", policy.international_posts_per_day),
        ):
            remaining = max(0, quota - existing_by_bucket[bucket])
            if not remaining:
                candidates_by_bucket[bucket] = []
                continue
            cond = is_ethiopia_expr if bucket == "ethiopia" else is_intl_expr
            limit_n = 250
            bucket_cfg = raw_content_filters.get(bucket, {})

            chosen_candidates = []
            for tier_hours in freshness_tiers:
                recency_cutoff = now - timedelta(hours=tier_hours)
                freshness_cond = or_(
                    NewsEvent.last_seen_at >= recency_cutoff,
                    NewsEvent.created_at >= recency_cutoff,
                    NewsEvent.first_article_published_at >= recency_cutoff,
                )
                if bypass_breaking:
                    event_eligibility_cond = or_(freshness_cond, NewsEvent.breaking_candidate.is_(True))
                else:
                    event_eligibility_cond = freshness_cond

                stmt = (
                    select(NewsEvent)
                    .where(
                        ~NewsEvent.id.in_(already_event_ids),
                        NewsEvent.review_required.is_(False),
                        cond,
                        event_eligibility_cond,
                    )
                    .order_by(
                        NewsEvent.created_at.desc(),
                        NewsEvent.last_seen_at.desc().nullslast(),
                        NewsEvent.trend_score.desc().nullslast(),
                    )
                    .limit(limit_n)
                )
                raw_candidates = list(session.scalars(stmt).all())

                tier_candidates = []
                for event in raw_candidates:
                    if _is_sponsored_event(event):
                        continue
                    if not _passes_bucket_filters(event, bucket_cfg):
                        continue
                    tier_candidates.append(event)

                chosen_candidates = tier_candidates
                if len(chosen_candidates) >= remaining:
                    break
                if tier_hours > freshness_h:
                    logger.warning(
                        "telegram_candidate_freshness_fallback",
                        bucket=bucket,
                        tier_hours=tier_hours,
                        found=len(chosen_candidates),
                        needed=remaining,
                    )

            if bucket == "ethiopia":
                chosen_candidates = sorted(
                    chosen_candidates,
                    key=lambda e: (
                        _amharic_enough(e.title),
                        getattr(e, "created_at", None) or getattr(e, "last_seen_at", None) or datetime.min.replace(tzinfo=UTC),
                        getattr(e, "trend_score", 0.0) or 0.0,
                    ),
                    reverse=True,
                )
            candidates_by_bucket[bucket] = chosen_candidates
    except Exception:
        session.rollback()
        logger.exception("plan_telegram_posts_task_error")
        raise
    finally:
        session.close()

    planned: list[str] = []
    for bucket, quota, language in (
        ("ethiopia", policy.ethiopia_posts_per_day, "am"),
        ("international", policy.international_posts_per_day, "en"),
    ):
        remaining = max(0, quota - existing_by_bucket[bucket])
        if not remaining:
            continue
        candidate_events = candidates_by_bucket.get(bucket, [])

        for event in candidate_events:
            if event.id in already_event_ids or remaining <= 0:
                continue
            headline, description, highlights = event.title, event.summary or "", []
            if language == "am":
                translation_ok = False
                if _amharic_enough(event.title):
                    headline, description, highlights = event.title, event.summary or "", []
                    translation_ok = True
                else:
                    try:
                        trans_session = SessionLocal()
                        try:
                            bound_event = trans_session.get(NewsEvent, event.id) or event
                            trans_svc = EditorialTranslationService(trans_session, get_translation_provider())
                            draft = trans_svc.translate_editorial(
                                EditorialTranslationRequest(
                                    event_id=bound_event.id,
                                    headline=bound_event.title,
                                    dek=bound_event.summary,
                                    category=bound_event.primary_category,
                                    target_language="am",
                                    theme="broadcast_impact",
                                    content_mode="single_card",
                                )
                            )
                            headline, description, highlights = draft.headline, draft.dek, draft.punchline_words
                            translation_ok = True
                        finally:
                            trans_session.close()
                    except Exception as exc:
                        logger.warning("telegram_editorial_translation_failed", event_id=str(event.id), error=str(exc))
                        headline, description, highlights = event.title, event.summary or "", []
                        translation_ok = True
                if not translation_ok:
                    continue

            img_session = SessionLocal()
            try:
                bound_img_event = img_session.get(NewsEvent, event.id) or event
                img_pipeline = ImagePipeline(img_session, get_text_provider(), get_image_provider())
                candidates = img_pipeline.browse_photos(bound_img_event).items
                valid_candidates = [
                    c for c in candidates
                    if c.image_url and "telesco.pe" not in c.image_url.lower() and c.image_url.startswith("http")
                ]
                photo = valid_candidates[0] if valid_candidates else None
            except Exception as exc:
                logger.warning("telegram_photo_browse_failed", event_id=str(event.id), error=str(exc))
                photo = None
            finally:
                img_session.close()

            source = "ETHIOPIAN TIMES"
            channel_handle = policy.channel_username if policy.channel_username.startswith("@") else f"@{policy.channel_username}"
            caption = f"Follow {channel_handle} for verified news updates."

            ins_session = SessionLocal()
            try:
                existing = ins_session.scalars(
                    select(TelegramPost).where(
                        TelegramPost.event_id == event.id,
                        TelegramPost.content_bucket == bucket,
                    )
                ).first()
                if existing:
                    if not policy.dry_run and (existing.dry_run or existing.status == "simulated" or _is_test_post(existing)):
                        ins_session.delete(existing)
                        ins_session.flush()
                    else:
                        already_event_ids.add(event.id)
                        continue

                slot_time = _telegram_slot(policy, len(counted_posts) + len(planned), now, scheduled_hours_today)
                scheduled_hours_today.add(slot_time.astimezone(zone).hour)

                post = TelegramPost(
                    event_id=event.id,
                    content_bucket=bucket,
                    language=language,
                    headline=headline,
                    description=description,
                    caption=caption,
                    source_attribution=source,
                    photo_url=photo.image_url if photo else None,
                    photo_credit=photo.photographer if photo else None,
                    highlight_words=highlights,
                    highlight_color=policy.highlight_color,
                    event_seen_at=getattr(event, "first_article_published_at", None) or event.last_seen_at or event.created_at,
                    scheduled_at=slot_time,
                    dry_run=policy.dry_run,
                    policy_snapshot={"timezone": policy.timezone, "channel": policy.channel_username},
                )
                ins_session.add(post)
                ins_session.commit()
                ins_session.refresh(post)
                post_id_str = str(post.id)
                already_event_ids.add(event.id)
                planned.append(f"{bucket}:{post_id_str}")
                remaining -= 1
            except Exception:
                ins_session.rollback()
                logger.exception("telegram_post_insert_failed", event_id=str(event.id))
            finally:
                ins_session.close()

    return {"planned": len(planned), "post_ids": [value.split(":", 1)[1] for value in planned]}


@celery_app.task(name="app.workers.tasks.publish_due_telegram_posts")
def publish_due_telegram_posts() -> dict:
    """Deliver due Telegram ledger rows, preserving idempotency by status."""
    from sqlalchemy import and_, or_, select
    from app.integrations.publishers.telegram import TelegramPublisher
    from app.models.telegram_post import TelegramPost, TelegramPublishingSettings

    session = SessionLocal()
    due_post_ids: list = []
    channel_username = ""
    is_dry_run = True
    try:
        policy = session.get(TelegramPublishingSettings, 1)
        if policy is None or not policy.enabled:
            return {"published": 0, "reason": "telegram_automation_disabled"}

        channel_username = policy.channel_username
        is_dry_run = policy.dry_run

        stalled_cut = datetime.now(UTC) - timedelta(minutes=10)
        stmt = (
            select(TelegramPost)
            .where(
                or_(
                    and_(
                        TelegramPost.status == "scheduled",
                        TelegramPost.scheduled_at <= datetime.now(UTC),
                    ),
                    and_(
                        TelegramPost.status == "publishing",
                        TelegramPost.scheduled_at <= stalled_cut,
                        TelegramPost.telegram_message_id.is_(None),
                    ),
                )
            )
            .order_by(TelegramPost.scheduled_at)
            .limit(10)
            .with_for_update(skip_locked=True)
        )
        due_posts = list(session.scalars(stmt).all())
        if not due_posts:
            return {"published": 0, "dry_run": is_dry_run}

        for post in due_posts:
            post.status = "publishing"
            due_post_ids.append(post.id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("publish_due_telegram_posts_task_error")
        raise
    finally:
        session.close()

    publisher = TelegramPublisher()
    delivered = 0
    for post_id in due_post_ids:
        post_session = SessionLocal()
        try:
            post = post_session.get(TelegramPost, post_id)
            if not post or post.status != "publishing":
                continue

            post.dry_run = is_dry_run
            result = publisher.publish(post, channel_username, dry_run=is_dry_run)
            if result.error:
                post.status, post.error = "failed", result.error[:2000]
            else:
                post.status = "simulated" if is_dry_run else "published"
                post.telegram_message_id = result.message_id
                post.published_at = result.published_at
                delivered += 1
            post_session.commit()
        except Exception as exc:
            post_session.rollback()
            logger.exception("publish_single_telegram_post_error", post_id=str(post_id), error=str(exc))
            try:
                err_session = SessionLocal()
                p = err_session.get(TelegramPost, post_id)
                if p and p.status == "publishing":
                    p.status, p.error = "failed", f"Worker delivery exception: {exc}"[:2000]
                    err_session.commit()
                err_session.close()
            except Exception:
                pass
        finally:
            post_session.close()

    return {"published": delivered, "dry_run": is_dry_run}
