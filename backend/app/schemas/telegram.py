"""Typed HTTP contracts for Telegram publishing. No secret fields are exposed."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TelegramPublishingSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    enabled: bool
    dry_run: bool
    channel_username: str
    timezone: str
    posts_per_day: int
    ethiopia_posts_per_day: int
    international_posts_per_day: int
    posting_hours: list[int]
    highlight_color: str
    bot_configured: bool = False
    updated_at: datetime


class TelegramPublishingSettingsUpdate(BaseModel):
    enabled: bool | None = None
    dry_run: bool | None = None
    channel_username: str | None = Field(default=None, min_length=3, max_length=128)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    posts_per_day: int | None = Field(default=None, ge=0, le=24)
    ethiopia_posts_per_day: int | None = Field(default=None, ge=0, le=24)
    international_posts_per_day: int | None = Field(default=None, ge=0, le=24)
    posting_hours: list[int] | None = Field(default=None, min_length=1, max_length=24)
    highlight_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_hours(self):
        if self.posting_hours is not None and (any(hour < 0 or hour > 23 for hour in self.posting_hours) or len(set(self.posting_hours)) != len(self.posting_hours)):
            raise ValueError("posting_hours must contain unique hours from 0 through 23")
        return self


class TelegramPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    content_bucket: str
    language: str
    headline: str
    description: str
    caption: str
    source_attribution: str
    photo_url: str | None
    photo_credit: str | None
    highlight_words: list[str]
    highlight_color: str
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    telegram_message_id: str | None
    dry_run: bool
    error: str | None
    created_at: datetime


class TelegramTestPostRequest(BaseModel):
    event_id: uuid.UUID | None = None
    force_live: bool = True
    channel_username: str | None = None


class TelegramTestPostResponse(BaseModel):
    success: bool
    message: str
    telegram_message_id: str | None = None
    post_id: uuid.UUID | None = None
    headline: str | None = None
    channel: str | None = None
    photo_url: str | None = None
    status: str | None = None
