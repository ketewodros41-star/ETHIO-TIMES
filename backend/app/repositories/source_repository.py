"""Data-access layer for news sources."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import SourceHealthStatus, SourceType
from app.models.news_source import NewsSource


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, source_id: uuid.UUID) -> NewsSource | None:
        return self.session.get(NewsSource, source_id)

    def get_by_slug(self, slug: str) -> NewsSource | None:
        return self.session.scalar(
            select(NewsSource).where(NewsSource.slug == slug)
        )

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        is_active: bool | None = None,
        source_type: SourceType | None = None,
        search: str | None = None,
    ) -> tuple[list[NewsSource], int]:
        stmt = select(NewsSource)
        count_stmt = select(func.count()).select_from(NewsSource)

        if is_active is not None:
            stmt = stmt.where(NewsSource.is_active == is_active)
            count_stmt = count_stmt.where(NewsSource.is_active == is_active)
        if source_type is not None:
            stmt = stmt.where(NewsSource.source_type == source_type)
            count_stmt = count_stmt.where(NewsSource.source_type == source_type)
        if search:
            pattern = f"%{search.lower()}%"
            criteria = or_(
                func.lower(NewsSource.name).like(pattern),
                func.lower(NewsSource.slug).like(pattern),
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        total = self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(NewsSource.name).limit(limit).offset(offset)
        items = list(self.session.scalars(stmt).all())
        return items, total

    def list_active_rss_sources(self) -> list[NewsSource]:
        stmt = select(NewsSource).where(
            NewsSource.is_active.is_(True),
            NewsSource.rss_url.is_not(None),
        )
        return list(self.session.scalars(stmt).all())

    def list_active_ids(self) -> list[uuid.UUID]:
        stmt = select(NewsSource.id).where(NewsSource.is_active.is_(True))
        return list(self.session.scalars(stmt).all())

    def create(self, source: NewsSource) -> NewsSource:
        self.session.add(source)
        self.session.flush()
        return source

    def delete(self, source: NewsSource) -> None:
        self.session.delete(source)

    def mark_success(self, source: NewsSource, ingested_count: int) -> None:
        now = datetime.now(UTC)
        source.last_checked_at = now
        source.last_success_at = now
        source.consecutive_failures = 0
        source.health_status = SourceHealthStatus.healthy
        source.total_articles_ingested += ingested_count

    def mark_failure(self, source: NewsSource, error: str) -> None:
        now = datetime.now(UTC)
        source.last_checked_at = now
        source.last_error_at = now
        source.last_error_message = error[:2000]
        source.consecutive_failures += 1
        source.health_status = (
            SourceHealthStatus.failing
            if source.consecutive_failures >= 3
            else SourceHealthStatus.degraded
        )
