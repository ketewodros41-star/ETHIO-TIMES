"""VisualAsset and SocialPost ORM models (Phase 5)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    InstagramPostFormat,
    SocialPlatform,
    SocialPostStatus,
    VisualAssetStatus,
)

if TYPE_CHECKING:
    from app.models.news_event import NewsEvent

class VisualAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "visual_assets"
    __table_args__ = (
        {"comment": "Gemini-generated editorial images for news events (Phase 5)."}
    )
    
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("news_events.id", ondelete="CASCADE"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    visual_strategy: Mapped[dict] = mapped_column(JSONB, default=dict)
    provider: Mapped[str] = mapped_column(String(64), default="mock")
    model: Mapped[str | None] = mapped_column(String(128))
    style: Mapped[str | None] = mapped_column(String(128))
    storage_path: Mapped[str | None] = mapped_column(String(2048))
    storage_url: Mapped[str | None] = mapped_column(String(2048))
    quality_score: Mapped[int | None] = mapped_column(Integer)
    quality_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[VisualAssetStatus] = mapped_column(Enum(VisualAssetStatus), default=VisualAssetStatus.generating)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    
    event: Mapped[NewsEvent] = relationship(back_populates="visual_assets")
    post: Mapped[SocialPost | None] = relationship(back_populates="visual_asset")


class SocialPost(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "social_posts"
    __table_args__ = (
        {"comment": "Composed Instagram posts in the publish pipeline (Phase 5)."}
    )
    
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("news_events.id", ondelete="CASCADE"), index=True)
    visual_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("visual_assets.id", ondelete="SET NULL"), index=True)
    platform: Mapped[SocialPlatform] = mapped_column(Enum(SocialPlatform), default=SocialPlatform.instagram)
    format: Mapped[InstagramPostFormat] = mapped_column(Enum(InstagramPostFormat), default=InstagramPostFormat.portrait)
    theme: Mapped[str] = mapped_column(String(64))
    headline: Mapped[str] = mapped_column(Text)
    caption: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_attribution: Mapped[str | None] = mapped_column(Text)
    key_facts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    media_path: Mapped[str | None] = mapped_column(String(2048))
    media_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[SocialPostStatus] = mapped_column(Enum(SocialPostStatus), default=SocialPostStatus.draft)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ig_media_id: Mapped[str | None] = mapped_column(String(128))
    ig_post_id: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[str | None] = mapped_column(Text)
    eligibility_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    event: Mapped[NewsEvent] = relationship(back_populates="social_posts")
    visual_asset: Mapped[VisualAsset | None] = relationship(back_populates="post")
