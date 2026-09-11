"""Data-access layer for articles."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.article import Article
from app.models.enums import ArticleStatus, ProcessingStatus


_ARTICLE_BEAT_SYNONYMS: dict[str, list[str]] = {
    "politics": ["politics", "governance", "election", "parliament", "political", "government"],
    "economy": ["economy", "business", "finance", "banking", "market", "trade", "investment", "economic", "fortune", "capital"],
    "sports": ["sports", "sport", "football", "athletics", "olympic", "soccer", "marathon"],
    "technology": ["technology", "tech", "telecom", "innovation", "digital", "ai", "software"],
    "tech": ["technology", "tech", "telecom", "innovation", "digital", "ai", "software"],
    "culture": ["culture", "society", "art", "heritage", "entertainment", "music", "diaspora", "community"],
    "breaking": ["breaking", "urgent", "accident", "incident", "alert", "telegram"],
    "conflict": ["conflict", "security", "military", "defense", "clash", "fano", "tplf", "war", "peace"],
}


class ArticleRepository:

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, article_id: uuid.UUID) -> Article | None:
        return self.session.get(Article, article_id)

    def get_with_source(self, article_id: uuid.UUID) -> Article | None:
        return self.session.scalar(
            select(Article)
            .options(
                selectinload(Article.source),
                selectinload(Article.analysis),
                selectinload(Article.event_links),
            )
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
        category: str | None = None,
        sort: str = "newest",
    ) -> tuple[list[Article], int]:
        stmt = select(Article).options(selectinload(Article.event_links))
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
        if category:
            cat_clean = category.strip().lower()
            synonyms = _ARTICLE_BEAT_SYNONYMS.get(cat_clean, [cat_clean])
            cat_filters = []
            for syn in synonyms:
                pattern = f"%{syn}%"
                cat_filters.append(func.cast(Article.categories, String).ilike(pattern))
                cat_filters.append(func.lower(Article.title).like(pattern))
                cat_filters.append(func.lower(Article.summary).like(pattern))
            cat_cond = or_(*cat_filters)
            stmt = stmt.where(cat_cond)
            count_stmt = count_stmt.where(cat_cond)

        total = self.session.scalar(count_stmt) or 0
        if sort == "oldest":
            order = (
                Article.published_at.asc().nullslast(),
                Article.created_at.asc(),
            )
        elif sort == "relevance":
            order = (
                Article.ethiopia_relevance_score.desc().nullslast(),
                Article.published_at.desc().nullslast(),
                Article.created_at.desc(),
            )
        elif sort == "importance":
            order = (
                Article.importance_score.desc().nullslast(),
                Article.published_at.desc().nullslast(),
                Article.created_at.desc(),
            )
        else:
            order = (
                Article.published_at.desc().nullslast(),
                Article.created_at.desc(),
            )

        stmt = stmt.order_by(*order).limit(limit).offset(offset)
        items = list(self.session.scalars(stmt).all())
        return items, total

    def add(self, article: Article) -> Article:
        self.session.add(article)
        self.session.flush()
        return article

    # ---- Pipeline selection & locking ----
    def select_processable_ids(
        self,
        *,
        limit: int = 50,
        statuses: list[ProcessingStatus] | None = None,
    ) -> list[uuid.UUID]:
        """IDs of articles that still need pipeline work (not terminal)."""
        active = statuses or [
            ProcessingStatus.pending,
            ProcessingStatus.relevance_scored,
            ProcessingStatus.analyzed,
            ProcessingStatus.embedded,
            ProcessingStatus.failed,
        ]
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

    def recent_candidates(
        self,
        *,
        limit: int = 50,
        exclude_id: uuid.UUID | None = None,
        published_after: datetime | None = None,
    ) -> list[Article]:
        """Fetch recently published or fetched articles for heuristic clustering."""
        stmt = select(Article)
        if exclude_id is not None:
            stmt = stmt.where(Article.id != exclude_id)
        if published_after is not None:
            stmt = stmt.where(
                (Article.published_at.is_(None))
                | (Article.published_at >= published_after)
            )
        stmt = stmt.order_by(Article.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())
