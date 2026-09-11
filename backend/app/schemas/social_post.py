"""Pydantic schemas for social posts and visual assets (Phase 5)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    InstagramPostFormat,
    SocialPlatform,
    SocialPostStatus,
    VisualAssetStatus,
)

class VisualAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    prompt: str
    visual_strategy: dict
    provider: str
    model: str | None
    style: str | None
    storage_url: str | None
    quality_score: int | None
    quality_report: dict
    status: VisualAssetStatus
    is_selected: bool
    created_at: datetime


class CarouselSlide(BaseModel):
    slide_number: int
    total_slides: int
    slide_type: str
    header: str
    body_text: str | None = None
    bullet_points: list[str] = Field(default_factory=list)
    source_attribution: str | None = None
    accent: str = "green"


class SocialPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    platform: SocialPlatform
    format: InstagramPostFormat
    theme: str
    headline: str
    caption: str
    hashtags: list[str]
    source_attribution: str | None
    key_facts: list[str]
    media_url: str | None
    status: SocialPostStatus
    scheduled_at: datetime | None
    published_at: datetime | None
    ig_post_id: str | None
    error: str | None
    eligibility_snapshot: dict
    visual_asset: VisualAssetRead | None
    carousel_slides: list[CarouselSlide] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SocialPostCompose(BaseModel):
    event_id: uuid.UUID
    format: InstagramPostFormat = InstagramPostFormat.portrait
    theme: str | None = Field(default=None, description="None = auto-select")


class SocialPostSchedule(BaseModel):
    scheduled_at: datetime


class SocialPostPatch(BaseModel):
    """Human edits — draft only."""
    headline: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None


class EligibilityCheck(BaseModel):
    eligible: bool
    blocked_reasons: list[str]
    verification_score: int
    review_required: bool
    auto_publish_eligible: bool


class ComposeTaskResponse(BaseModel):
    task_id: str
    post_id: uuid.UUID | None  # None when async via Celery
    message: str


class PhotoCandidate(BaseModel):
    id: str
    title: str
    thumb_url: str
    image_url: str
    source: str  # "telegram" | "article" | "wikimedia" | "pexels" | "openverse" | "web_search"
    photographer: str
    description: str | None = None
    entity_type: str = "lead"  # "lead" | "person" | "location" | "institution" | "concept"
    entity_name: str | None = None


class SelectCandidateRequest(BaseModel):
    event_id: uuid.UUID
    image_url: str
    title: str = "Editorial Photo"
    photographer: str = "Wikimedia Commons"
    source: str = "wikimedia"


class PhotoBrowseResponse(BaseModel):
    items: list[PhotoCandidate]
    page: int
    total_pages: int
    total_items: int
    has_next: bool
    has_prev: bool
    topic: str
    detected_country: str | None = None
    detected_country_code: str | None = None
    detected_person: str | None = None
    detected_persons: list[str] = Field(default_factory=list)
    detected_locations: list[str] = Field(default_factory=list)
    detected_institutions: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    suggested_chips: list[str] = Field(default_factory=list)


class EditorialTranslationRequest(BaseModel):
    event_id: uuid.UUID | None = None
    headline: str
    dek: str | None = None
    category: str | None = None
    target_language: str = "am"
    source_language: str = "en"
    format: str = "portrait"
    template: str = "single"
    slide_headers: list[str] = Field(default_factory=list)
    slide_bodies: list[str] = Field(default_factory=list)


class EditorialTranslationResponse(BaseModel):
    headline: str
    dek: str
    category: str
    punchline_words: list[str] = Field(default_factory=list)
    slide_headers: list[str] = Field(default_factory=list)
    slide_bodies: list[str] = Field(default_factory=list)
    translated_language: str = "am"



