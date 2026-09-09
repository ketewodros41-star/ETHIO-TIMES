"""Small helpers to create ORM rows in integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.article import Article
from app.models.enums import ArticleStatus, SourceType
from app.models.news_source import NewsSource
from sqlalchemy.orm import Session

_counter = {"n": 0}


def make_source(
    session: Session, *, slug: str | None = None, name: str = "Test Source"
) -> NewsSource:
    _counter["n"] += 1
    slug = slug or f"test-source-{_counter['n']}"
    source = NewsSource(
        name=name,
        slug=slug,
        source_type=SourceType.independent_media,
        country="ET",
        language="en",
    )
    session.add(source)
    session.flush()
    return source


def make_article(
    session: Session,
    source: NewsSource,
    *,
    title: str,
    summary: str | None = None,
    content: str | None = None,
    canonical_url: str | None = None,
    published_at: datetime | None = None,
) -> Article:
    _counter["n"] += 1
    article = Article(
        source_id=source.id,
        canonical_url=canonical_url or f"https://example.com/a/{_counter['n']}",
        url=canonical_url or f"https://example.com/a/{_counter['n']}",
        title=title,
        summary=summary,
        content=content,
        status=ArticleStatus.normalized,
        published_at=published_at or datetime.now(UTC),
        fetched_at=datetime.now(UTC),
    )
    session.add(article)
    session.flush()
    return article
