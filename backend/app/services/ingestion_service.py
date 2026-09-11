"""Ingestion orchestration.

Given a source, fetch items via the appropriate adapter, deduplicate by
canonical URL, score Ethiopia relevance (keyword stub), persist new articles,
update source health, and record a `PipelineJob`. All DB writes happen in the
caller's session; the Celery task is responsible for commit/rollback.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.article import Article
from app.models.audit import PipelineJob
from app.models.enums import ArticleStatus, JobStatus
from app.models.news_source import NewsSource
from app.pipelines.adapters.base import AdapterError, FetchedItem
from app.pipelines.adapters.factory import get_adapter_for_source
from app.pipelines.normalize import content_hash
from app.pipelines.relevance import score_relevance
from app.repositories.article_repository import ArticleRepository
from app.repositories.source_repository import SourceRepository

logger = get_logger(__name__)


class IngestionResult:
    def __init__(
        self,
        source_id: uuid.UUID,
        processed: int = 0,
        created: int = 0,
        status: JobStatus = JobStatus.success,
        error: str | None = None,
        created_ids: list[uuid.UUID] | None = None,
    ) -> None:
        self.source_id = source_id
        self.processed = processed
        self.created = created
        self.status = status
        self.error = error
        self.created_ids = created_ids or []

    def as_dict(self) -> dict:
        return {
            "source_id": str(self.source_id),
            "processed": self.processed,
            "created": self.created,
            "status": self.status.value,
            "error": self.error,
            "created_ids": [str(i) for i in self.created_ids],
        }


class IngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)
        self.articles = ArticleRepository(session)

    def ingest_source(
        self, source_id: uuid.UUID, celery_task_id: str | None = None
    ) -> IngestionResult:
        source = self.sources.get(source_id)
        if source is None:
            return IngestionResult(
                source_id, status=JobStatus.failed, error="source not found"
            )

        source_slug = source.slug
        job = self._start_job(source, celery_task_id)

        try:
            adapter = get_adapter_for_source(source)
            if not adapter.can_handle():
                return self._finish_skipped(
                    job, source, "no adapter can handle this source configuration"
                )

            items = adapter.fetch()
            processed, created, created_ids = self._persist_items(source, items)

            self.sources.mark_success(source, created)
            self._finish_job(job, JobStatus.success, processed, created)
            logger.info(
                "ingest_success", source=source_slug, processed=processed, created=created
            )
            return IngestionResult(
                source_id, processed, created, JobStatus.success, created_ids=created_ids
            )

        except (AdapterError, NotImplementedError) as exc:
            self.session.rollback()
            return self._finish_failed(job, source, str(exc))
        except Exception as exc:  # noqa: BLE001 - record any unexpected failure
            self.session.rollback()
            logger.exception("ingest_error", source=source_slug)
            return self._finish_failed(job, source, f"unexpected: {exc}")

    def _persist_items(
        self, source: NewsSource, items: list[FetchedItem]
    ) -> tuple[int, int, list[uuid.UUID]]:
        processed = 0
        created = 0
        created_ids: list[uuid.UUID] = []
        seen_batch_urls: set[str] = set()

        for item in items:
            processed += 1
            if not item.canonical_url or item.canonical_url in seen_batch_urls:
                continue
            if self.articles.exists_canonical_url(item.canonical_url):
                continue
            seen_batch_urls.add(item.canonical_url)

            article = self._build_article(source, item)
            try:
                with self.session.begin_nested():
                    self.articles.add(article)
                created += 1
                created_ids.append(article.id)
            except IntegrityError:
                # Race condition or duplicate within transaction
                continue

        return processed, created, created_ids

    def _build_article(self, source: NewsSource, item: FetchedItem) -> Article:
        score, keywords = score_relevance(item.title, item.summary, item.content)

        # Supabase Free Tier optimization:
        # 1. Truncate body text to 3,000 chars (plenty for NLP extraction & summary; original URL kept)
        # 2. Avoid duplicating full text across raw_content and raw_summary
        # 3. Strip bloat from raw_payload
        clean_content = (item.content or "").strip()
        truncated_content = clean_content[:3000] if clean_content else None
        clean_summary = (item.summary or "").strip()
        truncated_summary = clean_summary[:1000] if clean_summary else None

        clean_payload = {
            k: v
            for k, v in (item.raw_payload or {}).items()
            if k in {"id", "link", "channel", "tags", "has_photo"}
        }

        return Article(
            source_id=source.id,
            canonical_url=item.canonical_url,
            url=item.url,
            guid=item.guid,
            content_hash=content_hash(item.title, item.summary, item.content),
            raw_title=item.title[:500] if item.title else None,
            raw_summary=None,
            raw_content=None,
            raw_payload=clean_payload,
            title=item.title[:500] if item.title else None,
            summary=truncated_summary,
            content=truncated_content,
            author=item.author[:255] if item.author else None,
            language=item.language or source.language,
            categories=item.categories or [],
            image_url=item.image_url,
            ethiopia_relevance_score=score,
            relevance_keywords=keywords,
            status=ArticleStatus.normalized,
            published_at=item.published_at,
            fetched_at=datetime.now(UTC),
        )

    # ---- Pipeline job bookkeeping ----

    def _start_job(self, source: NewsSource, celery_task_id: str | None) -> PipelineJob:
        job = PipelineJob(
            task_name="ingest_source",
            celery_task_id=celery_task_id,
            source_id=source.id,
            status=JobStatus.running,
            started_at=datetime.now(UTC),
        )
        self.session.add(job)
        self.session.flush()
        return job

    def _finish_job(
        self, job: PipelineJob, status: JobStatus, processed: int, created: int
    ) -> None:
        job.status = status
        job.items_processed = processed
        job.items_created = created
        job.finished_at = datetime.now(UTC)

    def _finish_failed(
        self, job: PipelineJob, source: NewsSource, error: str
    ) -> IngestionResult:
        self.sources.mark_failure(source, error)
        job.status = JobStatus.failed
        job.error_message = error[:2000]
        job.finished_at = datetime.now(UTC)
        logger.warning("ingest_failed", source=source.slug, error=error)
        return IngestionResult(source.id, status=JobStatus.failed, error=error)

    def _finish_skipped(
        self, job: PipelineJob, source: NewsSource, reason: str
    ) -> IngestionResult:
        job.status = JobStatus.skipped
        job.error_message = reason
        job.finished_at = datetime.now(UTC)
        source.last_checked_at = datetime.now(UTC)
        return IngestionResult(source.id, status=JobStatus.skipped, error=reason)
