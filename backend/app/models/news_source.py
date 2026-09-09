"""`news_sources` — the registry of everything ETHIOTIMES ingests from."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SourceHealthStatus, SourceType, VerificationStatus


class NewsSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_sources"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_news_sources_slug"),
        {"comment": "Registry of news sources ETHIOTIMES monitors and ingests."},
    )

    # ---- Identity ----
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Endpoints ----
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    rss_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    api_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # ---- Classification ----
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=True),
        nullable=False,
        index=True,
    )
    country: Mapped[str] = mapped_column(String(64), nullable=False, default="ET")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")

    # ---- Trust & coverage ----
    trust_profile: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    coverage_categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    ethiopia_relevance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    is_primary_source: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ---- Verification (esp. Telegram handles) ----
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=True),
        nullable=False,
        default=VerificationStatus.unverified,
        server_default=VerificationStatus.unverified.value,
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Scheduling & activation ----
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    crawl_frequency_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Health ----
    health_status: Mapped[SourceHealthStatus] = mapped_column(
        Enum(SourceHealthStatus, name="source_health_status", native_enum=True),
        nullable=False,
        default=SourceHealthStatus.unknown,
        server_default=SourceHealthStatus.unknown.value,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_articles_ingested: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # ---- Relationships ----
    articles: Mapped[list["Article"]] = relationship(  # noqa: F821
        back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NewsSource {self.slug} ({self.source_type.value})>"
