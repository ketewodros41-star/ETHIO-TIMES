"""Data-access layer for news events, memberships, and timelines."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.article import Article
from app.models.enums import EventStatus
from app.models.news_event import EventArticle, EventTimeline, NewsEvent


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, event_id: uuid.UUID) -> NewsEvent | None:
        return self.session.get(NewsEvent, event_id)

    def get_detail(self, event_id: uuid.UUID) -> NewsEvent | None:
        return self.session.scalar(
            select(NewsEvent)
            .options(
                selectinload(NewsEvent.article_links)
                .selectinload(EventArticle.article)
                .selectinload(Article.source),
                selectinload(NewsEvent.timeline),
            )
            .where(NewsEvent.id == event_id)
        )

    def event_for_article(self, article_id: uuid.UUID) -> NewsEvent | None:
        """Return the event an article belongs to (if any)."""
        return self.session.scalar(
            select(NewsEvent)
            .join(EventArticle, EventArticle.event_id == NewsEvent.id)
            .where(EventArticle.article_id == article_id)
            .limit(1)
        )

    def membership(
        self, event_id: uuid.UUID, article_id: uuid.UUID
    ) -> EventArticle | None:
        return self.session.scalar(
            select(EventArticle).where(
                EventArticle.event_id == event_id,
                EventArticle.article_id == article_id,
            )
        )

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: EventStatus | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> tuple[list[NewsEvent], int]:
        stmt = select(NewsEvent)
        count_stmt = select(func.count()).select_from(NewsEvent)
        if status is not None:
            stmt = stmt.where(NewsEvent.status == status)
            count_stmt = count_stmt.where(NewsEvent.status == status)
        if category:
            stmt = stmt.where(NewsEvent.primary_category == category)
            count_stmt = count_stmt.where(NewsEvent.primary_category == category)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(func.lower(NewsEvent.title).like(pattern))
            count_stmt = count_stmt.where(func.lower(NewsEvent.title).like(pattern))

        total = self.session.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(
                NewsEvent.last_seen_at.desc().nullslast(),
                NewsEvent.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all()), total

    def add(self, event: NewsEvent) -> NewsEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def add_membership(self, link: EventArticle) -> EventArticle:
        self.session.add(link)
        self.session.flush()
        return link

    def add_timeline(self, entry: EventTimeline) -> EventTimeline:
        self.session.add(entry)
        self.session.flush()
        return entry

    def member_articles(self, event_id: uuid.UUID) -> list[Article]:
        return list(
            self.session.scalars(
                select(Article)
                .join(EventArticle, EventArticle.article_id == Article.id)
                .where(EventArticle.event_id == event_id)
            ).all()
        )
