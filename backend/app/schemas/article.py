"""Pydantic schemas for articles."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArticleStatus


class ArticleSourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


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


class ArticleDetail(ArticleRead):
    content: str | None = None
    raw_title: str | None = None
    raw_summary: str | None = None
    guid: str | None = None
    content_hash: str | None = None
    source: ArticleSourceRef | None = None
