"""Pydantic schemas for articles."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArticleStatus, ProcessingStatus, RelevanceDecision


class ArticleSourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class ArticleAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: str | None = None
    language_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    importance: int
    summary: str | None = None
    entities: dict = Field(default_factory=dict)
    topics: list = Field(default_factory=list)
    dates: list = Field(default_factory=list)
    money: list = Field(default_factory=list)
    statistics: list = Field(default_factory=list)
    model: str | None = None


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    canonical_url: str
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    author: str | None = None
    language: str | None = None
    categories: list[str] = Field(default_factory=list)
    image_url: str | None = None
    ethiopia_relevance_score: float
    relevance_keywords: list[str] = Field(default_factory=list)
    status: ArticleStatus
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    created_at: datetime

    # ---- Intelligence (Phase 2) ----
    processing_status: ProcessingStatus
    relevance_score: int | None = None
    relevance_decision: RelevanceDecision | None = None
    is_ethiopia_related: bool | None = None
    primary_region: str | None = None
    detected_language: str | None = None
    importance_score: float
    event_id: uuid.UUID | None = None


class ArticleDetail(ArticleRead):
    content: str | None = None
    raw_title: str | None = None
    raw_summary: str | None = None
    guid: str | None = None
    content_hash: str | None = None
    relevance_reason: str | None = None
    source: ArticleSourceRef | None = None
    analysis: ArticleAnalysisRead | None = None
