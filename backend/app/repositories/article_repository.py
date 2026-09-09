"""Data-access layer for articles."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.article import Article
from app.models.enums import ArticleStatus


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
