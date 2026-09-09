"""Pydantic schemas for news events (Phase 2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ArticleRelationType,
    EventStatus,
    EventTimelineType,
    ProcessingStatus,
    RelevanceDecision,
)
from app.models.news_event import EventArticle, EventTimeline, NewsEvent


class SourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str


class ArticleSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    summary: str | None
    url: str | None
    published_at: datetime | None
    detected_language: str | None
    importance_score: float
    relevance_score: int | None
    relevance_decision: RelevanceDecision | None
    processing_status: ProcessingStatus
    category: str | None
    source: SourceRef | None


class EventArticleRead(BaseModel):
    relation_type: ArticleRelationType
    similarity_score: float
    confidence: float
    is_primary: bool
    article: ArticleSummary


class EventTimelineRead(BaseModel):
    id: uuid.UUID
    entry_type: EventTimelineType
    occurred_at: datetime
    title: str | None
    detail: dict
    article_id: uuid.UUID | None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    summary: str | None
    slug: str | None
    status: EventStatus
    primary_category: str | None
    primary_region: str | None
    categories: list[str]
    key_entities: list[str]
    significance_score: float
    cluster_confidence: float
    article_count: int
    source_count: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EventDetail(EventRead):
    articles: list[EventArticleRead]
    timeline: list[EventTimelineRead]


# --------------------------------------------------------------------------- #
# Serializers (build from ORM objects with loaded relationships)
# --------------------------------------------------------------------------- #
def _article_summary(article) -> ArticleSummary:  # noqa: ANN001
    return ArticleSummary(
        id=article.id,
        title=article.title,
        summary=article.summary,
        url=article.url,
        published_at=article.published_at,
        detected_language=article.detected_language,
        importance_score=article.importance_score,
        relevance_score=article.relevance_score,
        relevance_decision=article.relevance_decision,
        processing_status=article.processing_status,
        category=(article.analysis.category if article.analysis else None),
        source=SourceRef.model_validate(article.source) if article.source else None,
    )


def to_event_article(link: EventArticle) -> EventArticleRead:
    return EventArticleRead(
        relation_type=link.relation_type,
        similarity_score=link.similarity_score,
        confidence=link.confidence,
        is_primary=link.is_primary,
        article=_article_summary(link.article),
    )


def to_timeline(entry: EventTimeline) -> EventTimelineRead:
    return EventTimelineRead(
        id=entry.id,
        entry_type=entry.entry_type,
        occurred_at=entry.occurred_at,
        title=entry.title,
        detail=entry.detail or {},
        article_id=entry.article_id,
    )


def to_event_detail(event: NewsEvent) -> EventDetail:
    base = EventRead.model_validate(event).model_dump()
    # Primary first, then by similarity desc.
    links = sorted(
        event.article_links,
        key=lambda x: (not x.is_primary, -x.similarity_score),
    )
    timeline = sorted(event.timeline, key=lambda x: x.occurred_at)
    return EventDetail(
        **base,
        articles=[to_event_article(link) for link in links],
        timeline=[to_timeline(entry) for entry in timeline],
    )
