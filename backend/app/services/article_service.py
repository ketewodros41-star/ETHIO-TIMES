"""Business logic for reading articles."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.enums import ArticleStatus
from app.repositories.article_repository import ArticleRepository


class ArticleNotFoundError(Exception):
    pass


class ArticleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ArticleRepository(session)

    def list_articles(
        self,
        *,
        limit: int,
        offset: int,
        source_id: uuid.UUID | None,
        status: ArticleStatus | None,
        search: str | None,
        category: str | None = None,
        sort: str = "newest",
    ) -> tuple[list[Article], int]:
        return self.repo.list(
            limit=limit,
            offset=offset,
            source_id=source_id,
            status=status,
            search=search,
            category=category,
            sort=sort,
        )

    def get_article(self, article_id: uuid.UUID) -> Article:
        article = self.repo.get_with_source(article_id)
        if article is None:
            raise ArticleNotFoundError(str(article_id))
        return article
