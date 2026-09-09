"""Pydantic schemas for news sources."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SourceHealthStatus, SourceType, VerificationStatus


class SourceBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    website: str | None = None
    base_url: str | None = None
    rss_url: str | None = None
    api_url: str | None = None
    telegram_username: str | None = None
    telegram_url: str | None = None
    source_type: SourceType
    country: str = "ET"
    language: str = "en"
    trust_profile: dict = Field(default_factory=dict)
    coverage_categories: list[str] = Field(default_factory=list)
    ethiopia_relevance_score: float = 0.0
    is_primary_source: bool = False
    verification_status: VerificationStatus = VerificationStatus.unverified
    verification_notes: str | None = None
    is_active: bool = True
    crawl_frequency_minutes: int = 30


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    """All fields optional for PATCH-style updates."""

    name: str | None = None
    description: str | None = None
    website: str | None = None
    base_url: str | None = None
    rss_url: str | None = None
    api_url: str | None = None
    telegram_username: str | None = None
    telegram_url: str | None = None
    source_type: SourceType | None = None
    country: str | None = None
    language: str | None = None
    trust_profile: dict | None = None
    coverage_categories: list[str] | None = None
    ethiopia_relevance_score: float | None = None
    is_primary_source: bool | None = None
    verification_status: VerificationStatus | None = None
    verification_notes: str | None = None
    is_active: bool | None = None
    crawl_frequency_minutes: int | None = None


class SourceRead(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_status: SourceHealthStatus
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    consecutive_failures: int
    total_articles_ingested: int
    created_at: datetime
    updated_at: datetime


class SourceHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    source_type: SourceType
    is_active: bool
    health_status: SourceHealthStatus
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    consecutive_failures: int
    total_articles_ingested: int
