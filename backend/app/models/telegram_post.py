"""Telegram-only publishing policy and delivery ledger.

These tables intentionally do not reuse ``social_posts``: Telegram cards,
captions, delivery IDs, and scheduling policy must stay independent from the
Instagram/Photo Studio workflow.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


DEFAULT_BLOCKED_KEYWORDS: list[str] = [
    "sponsored",
    "advertisement",
    "advertorial",
    "press release",
    "partner content",
    "ad feature",
    "promoted",
    "ማስታወቂያ",
    "ማስተዋወቂያ",
    "ስፖንሰር",
    "የስፖንሰር",
    "ስፖንሰር የተደረገ",
    "የተከፈለበት",
    "የንግድ ማስታወቂያ",
    "ጋዜጣዊ መግለጫ",
    "አጋር ይዘት",
    "ኢትዮ ቴሌኮም",
    "ቴሌብር",
    "ልዩ ቅናሽ",
]


def _default_content_filters() -> dict:
    return {
        "ethiopia": {
            "allowed_categories": [],
            "blocked_categories": [],
            "allowed_keywords": [],
            "blocked_keywords": list(DEFAULT_BLOCKED_KEYWORDS),
        },
        "international": {
            "allowed_categories": [],
            "blocked_categories": [],
            "allowed_keywords": [],
            "blocked_keywords": list(DEFAULT_BLOCKED_KEYWORDS),
        },
    }


class TelegramPublishingSettings(Base, TimestampMixin):
    __tablename__ = "telegram_publishing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    channel_username: Mapped[str] = mapped_column(String(128), nullable=False, default="@Ethiopantimes")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Addis_Ababa")
    posts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    ethiopia_posts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    international_posts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    posting_hours: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: [8, 11, 14, 17, 20], server_default="[8, 11, 14, 17, 20]")
    highlight_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#00F0FF")
    # Per-bucket topic/category and keyword filter configuration.
    # Empty allowed_categories means "allow all"; non-empty means "allow only these".
    content_filters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=_default_content_filters,
        server_default="""'{
          "ethiopia": {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["sponsored", "advertisement", "advertorial", "press release", "partner content", "ad feature", "promoted", "ማስታወቂያ", "ማስተዋወቂያ", "ስፖንሰር", "የስፖንሰር", "ስፖንሰር የተደረገ", "የተከፈለበት", "የንግድ ማስታወቂያ", "ጋዜጣዊ መግለጫ", "አጋር ይዘት", "ኢትዮ ቴሌኮም", "ቴሌብር", "ልዩ ቅናሽ"]},
          "international": {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["sponsored", "advertisement", "advertorial", "press release", "partner content", "ad feature", "promoted", "ማስታወቂያ", "ማስተዋወቂያ", "ስፖንሰር", "የስፖንሰር", "ስፖንሰር የተደረገ", "የተከፈለበት", "የንግድ ማስታወቂያ", "ጋዜጣዊ መግለጫ", "አጋር ይዘት", "ኢትዮ ቴሌኮም", "ቴሌብር", "ልዩ ቅናሽ"]}
        }'::jsonb""",
    )


class TelegramPost(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "telegram_posts"
    __table_args__ = (
        UniqueConstraint("event_id", "content_bucket", name="uq_telegram_posts_event_bucket"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("news_events.id", ondelete="CASCADE"), nullable=False, index=True)
    content_bucket: Mapped[str] = mapped_column(String(24), nullable=False)  # ethiopia | international
    language: Mapped[str] = mapped_column(String(16), nullable=False)  # am | en
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    source_attribution: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    photo_credit: Mapped[str | None] = mapped_column(String(512), nullable=True)
    highlight_words: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    highlight_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#00F0FF")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled", server_default="scheduled", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    event = relationship("NewsEvent")
