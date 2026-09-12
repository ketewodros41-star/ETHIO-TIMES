from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublishingSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    posts_per_day: int
    automation_enabled: bool
    timezone: str
    updated_at: datetime


class PublishingSettingsUpdate(BaseModel):
    posts_per_day: int | None = Field(default=None, ge=0, le=24)
    automation_enabled: bool | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
