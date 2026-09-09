"""Verification tables (Phase 3): claims, evidence, contradictions.

Editorial later must only use claims that have at least one `claim_evidence`
row. Claims without evidence are not persisted by the extraction pipeline.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ClaimType, ContradictionSeverity


class EventClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "event_claims"
    __table_args__ = (
        {"comment": "Structured claims extracted from articles covering an event."},
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
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(
        Enum(ClaimType, name="claim_type", native_enum=True),
        nullable=False,
        index=True,
    )
    normalized_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entities: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    # Groups comparable claims across sources (type + entities + quantity kind).
    canonical_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, index=True
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5, server_default="0.5"
    )
    is_major: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    event: Mapped["NewsEvent"] = relationship(  # noqa: F821
        "NewsEvent", back_populates="claims"
    )
    article: Mapped["Article | None"] = relationship("Article")  # noqa: F821
    evidence: Mapped[list[ClaimEvidence]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimEvidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        UniqueConstraint("claim_id", "article_id", name="uq_claim_evidence_claim_article"),
        {"comment": "Source excerpts/URLs backing a claim. Editorial may only use evidenced claims."},
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    claim: Mapped[EventClaim] = relationship(back_populates="evidence")
    article: Mapped["Article"] = relationship("Article")  # noqa: F821
    source: Mapped["NewsSource | None"] = relationship("NewsSource")  # noqa: F821


class Contradiction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contradictions"
    __table_args__ = (
        {"comment": "Conflicting claims across sources covering the same event."},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("event_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[ContradictionSeverity] = mapped_column(
        Enum(ContradictionSeverity, name="contradiction_severity", native_enum=True),
        nullable=False,
        index=True,
    )
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    event: Mapped["NewsEvent"] = relationship(  # noqa: F821
        "NewsEvent", back_populates="contradictions"
    )
    claim_a: Mapped[EventClaim] = relationship(
        "EventClaim", foreign_keys=[claim_a_id]
    )
    claim_b: Mapped[EventClaim] = relationship(
        "EventClaim", foreign_keys=[claim_b_id]
    )
