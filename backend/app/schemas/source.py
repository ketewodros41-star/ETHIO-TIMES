"""Pydantic schemas for news sources."""

from __future__ import annotations

import uuid
from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SourceHealthStatus, SourceType, VerificationStatus

_SOURCE_TYPE_ALIASES: dict[str, SourceType] = {
    # RSS and web media
    "rss_feed": SourceType.independent_media,
    "rss": SourceType.independent_media,
    "feed": SourceType.independent_media,
    "news_site": SourceType.independent_media,
    "website": SourceType.independent_media,
    "web": SourceType.independent_media,
    "fact_checker": SourceType.independent_media,
    "blog": SourceType.independent_media,
    "online_media": SourceType.independent_media,
    # Telegram channels
    "telegram": SourceType.telegram_channel,
    "tg": SourceType.telegram_channel,
    "telegram_channel": SourceType.telegram_channel,
    "tg_channel": SourceType.telegram_channel,
    # Government and ministries
    "government_portal": SourceType.government,
    "gov": SourceType.government,
    "government": SourceType.government,
    "ministry": SourceType.government,
    "agency": SourceType.government_agency,
    "government_agency": SourceType.government_agency,
    # Public broadcasters & state media
    "public_broadcaster": SourceType.public_broadcaster,
    "broadcaster": SourceType.public_broadcaster,
    "tv": SourceType.public_broadcaster,
    "radio": SourceType.public_broadcaster,
    "state_media": SourceType.public_broadcaster,
    # National agencies
    "national_news_agency": SourceType.national_news_agency,
    "national_agency": SourceType.national_news_agency,
    "ena": SourceType.national_news_agency,
    # Business and finance
    "business_media": SourceType.business_media,
    "business": SourceType.business_media,
    "economy": SourceType.business_media,
    "finance": SourceType.business_media,
    "commercial": SourceType.business_media,
    # International media & wires
    "international_wire": SourceType.international_wire,
    "wire": SourceType.international_wire,
    "international_media": SourceType.international_media,
    "international": SourceType.international_media,
    # Research & financial institutions
    "research_institution": SourceType.research_institution,
    "research": SourceType.research_institution,
    "academic": SourceType.research_institution,
    "financial_institution": SourceType.financial_institution,
    "bank": SourceType.financial_institution,
    "social_signal": SourceType.social_signal,
    "social": SourceType.social_signal,
}


def normalize_source_type_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, SourceType):
        return v
    if isinstance(v, str):
        clean = v.strip().lower()
        if clean in _SOURCE_TYPE_ALIASES:
            return _SOURCE_TYPE_ALIASES[clean]
        try:
            return SourceType(clean)
        except ValueError:
            return SourceType.independent_media
    return v


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

    @field_validator("source_type", mode="before")
    @classmethod
    def validate_source_type(cls, v: Any) -> Any:
        return normalize_source_type_value(v)


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

    @field_validator("source_type", mode="before")
    @classmethod
    def validate_source_type(cls, v: Any) -> Any:
        return normalize_source_type_value(v)


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
