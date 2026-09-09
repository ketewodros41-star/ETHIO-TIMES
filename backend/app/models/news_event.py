"""`news_events` and `event_articles` — clustering stubs for later phases.

Phase 1 defines the schema so migrations and relationships are stable, but the
clustering / verification logic that populates these tables is out of scope
(Phase 2+). They are intentionally unused by the Phase 1 dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NewsEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_events"
    __table_args__ = (
        {"comment": "Clustered real-world events aggregating multiple articles."},
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    significance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    article_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    article_links: Mapped[list[EventArticle]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventArticle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_articles"
    __table_args__ = (
        UniqueConstraint("event_id", "article_id", name="uq_event_article"),
        {"comment": "Association between news_events and articles."},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    is_primary: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )

    event: Mapped[NewsEvent] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship(back_populates="event_links")  # noqa: F821
