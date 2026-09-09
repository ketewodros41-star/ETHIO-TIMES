"""`news_events`, `event_articles`, and `event_timeline` — clustering (Phase 2),
verification fields (Phase 3), and trend intelligence fields (Phase 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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
from app.models.article import EMBEDDING_DIM
from app.models.enums import (
    ArticleRelationType,
    EventStatus,
    EventTimelineType,
    EventVerificationStatus,
    EventVerifyStatus,
    TrendStatus,
)

if TYPE_CHECKING:
    from app.models.trending import EventVelocityMetric
    from app.models.verification import Contradiction, EventClaim


class NewsEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "news_events"
    __table_args__ = (
        {"comment": "Clustered real-world events aggregating multiple articles."},
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", native_enum=True),
        nullable=False,
        default=EventStatus.developing,
        server_default=EventStatus.developing.value,
        index=True,
    )
    primary_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    key_entities: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    significance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    cluster_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    article_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Cluster centroid (mean of member embeddings), used for fast NN matching.
    centroid_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    # first_seen_at == first_detected; last_seen_at == last_updated.
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # ---- Verification (Phase 3) ----
    # Public 0–100 score + status (unverified/developing/partially_confirmed/
    # confirmed/contradicted). Distinct from clustering `status` (EventStatus)
    # and source-handle VerificationStatus.
    verification_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    event_verification_status: Mapped[EventVerificationStatus] = mapped_column(
        Enum(
            EventVerificationStatus,
            name="event_verification_status",
            native_enum=True,
        ),
        nullable=False,
        default=EventVerificationStatus.unverified,
        server_default=EventVerificationStatus.unverified.value,
        index=True,
    )
    verification_explanation: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    primary_source_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    cited_institutions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    discovered_primary_source_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    review_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    auto_publish_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    verification_processing_status: Mapped[EventVerifyStatus] = mapped_column(
        Enum(EventVerifyStatus, name="event_verify_status", native_enum=True),
        nullable=False,
        default=EventVerifyStatus.pending,
        server_default=EventVerifyStatus.pending.value,
        index=True,
    )
    verification_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_verification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_lock_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Trend intelligence (Phase 4) ----
    trend_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    trend_status: Mapped[TrendStatus] = mapped_column(
        Enum(TrendStatus, name="trend_status", native_enum=True),
        nullable=False,
        default=TrendStatus.low,
        server_default=TrendStatus.low.value,
        index=True,
    )
    trend_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    editorial_importance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    breaking_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    trend_scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    article_links: Mapped[list[EventArticle]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    timeline: Mapped[list[EventTimeline]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventTimeline.occurred_at",
    )
    claims: Mapped[list[EventClaim]] = relationship(  # noqa: F821
        "EventClaim",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    contradictions: Mapped[list[Contradiction]] = relationship(  # noqa: F821
        "Contradiction",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    velocity_metrics: Mapped[list[EventVelocityMetric]] = relationship(  # noqa: F821
        "EventVelocityMetric",
        back_populates="event",
        cascade="all, delete-orphan",
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
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[ArticleRelationType] = mapped_column(
        Enum(ArticleRelationType, name="article_relation_type", native_enum=True),
        nullable=False,
        default=ArticleRelationType.primary,
        server_default=ArticleRelationType.primary.value,
    )
    similarity_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    is_primary: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )

    event: Mapped[NewsEvent] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship(back_populates="event_links")  # noqa: F821


class EventTimeline(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_timeline"
    __table_args__ = (
        {"comment": "Notable moments in the lifecycle of a news event."},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    entry_type: Mapped[EventTimelineType] = mapped_column(
        Enum(EventTimelineType, name="event_timeline_type", native_enum=True),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    event: Mapped[NewsEvent] = relationship(back_populates="timeline")
