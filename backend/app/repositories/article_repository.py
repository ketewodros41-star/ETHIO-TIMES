"""Data-access layer for articles."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.article import Article
from app.models.enums import ArticleStatus, ProcessingStatus


class ArticleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, article_id: uuid.UUID) -> Article | None:
        return self.session.get(Article, article_id)

    def get_with_source(self, article_id: uuid.UUID) -> Article | None:
        return self.session.scalar(
            select(Article)
            .options(selectinload(Article.source))
            .where(Article.id == article_id)
        )

    def get_by_canonical_url(self, canonical_url: str) -> Article | None:
        return self.session.scalar(
            select(Article).where(Article.canonical_url == canonical_url)
        )

    def exists_canonical_url(self, canonical_url: str) -> bool:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Article)
                .where(Article.canonical_url == canonical_url)
            )
            or 0
        ) > 0

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        source_id: uuid.UUID | None = None,
        status: ArticleStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Article], int]:
        stmt = select(Article)
        count_stmt = select(func.count()).select_from(Article)

        if source_id is not None:
            stmt = stmt.where(Article.source_id == source_id)
            count_stmt = count_stmt.where(Article.source_id == source_id)
        if status is not None:
            stmt = stmt.where(Article.status == status)
            count_stmt = count_stmt.where(Article.status == status)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(func.lower(Article.title).like(pattern))
            count_stmt = count_stmt.where(func.lower(Article.title).like(pattern))

        total = self.session.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(
                Article.published_at.desc().nullslast(),
                Article.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        items = list(self.session.scalars(stmt).all())
        return items, total

    def add(self, article: Article) -> Article:
        self.session.add(article)
        self.session.flush()
        return article

    # ---- Pipeline selection & locking ----
    def select_processable_ids(
        self, *, limit: int = 50, include_failed: bool = True
    ) -> list[uuid.UUID]:
        """IDs of articles that still need pipeline work (not terminal)."""
        active = [
            ProcessingStatus.pending,
            ProcessingStatus.relevance_scored,
            ProcessingStatus.analyzed,
            ProcessingStatus.embedded,
        ]
        if include_failed:
            active.append(ProcessingStatus.failed)
        stmt = (
            select(Article.id)
            .where(Article.processing_status.in_(active))
            .order_by(Article.created_at.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def lock_for_processing(self, article_id: uuid.UUID) -> Article | None:
        """Row-lock an article with SKIP LOCKED to prevent concurrent pipelines."""
        return self.session.scalar(
            select(Article)
            .where(Article.id == article_id)
            .with_for_update(skip_locked=True)
        )

    # ---- Vector nearest-neighbor (cosine) ----
    def nearest_by_embedding(
        self,
        embedding: list[float],
        *,
        limit: int = 25,
        exclude_id: uuid.UUID | None = None,
        published_after: datetime | None = None,
        only_embedded: bool = True,
    ) -> list[tuple[Article, float]]:
        """Return (article, cosine_similarity) neighbors, most similar first.

        cosine_similarity = 1 - cosine_distance, in [0, 1] for normalized vectors.
        """
        distance = Article.embedding.cosine_distance(embedding)
        stmt = select(Article, distance.label("distance"))
        if only_embedded:
            stmt = stmt.where(Article.embedding.isnot(None))
        if exclude_id is not None:
            stmt = stmt.where(Article.id != exclude_id)
        if published_after is not None:
            stmt = stmt.where(
                (Article.published_at.is_(None))
                | (Article.published_at >= published_after)
            )
        stmt = stmt.order_by(distance.asc()).limit(limit)

        results: list[tuple[Article, float]] = []
        for article, dist in self.session.execute(stmt).all():
            results.append((article, 1.0 - float(dist)))
        return results
