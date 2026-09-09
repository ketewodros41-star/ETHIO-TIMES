"""Enumerations used across ETHIOTIMES domain models.

These map to native PostgreSQL enum types via SQLAlchemy. Enum *values* are
lowercase snake_case strings and are what get stored in the database.
"""

from __future__ import annotations

import enum


class SourceType(str, enum.Enum):
    """Category of a news source in the registry."""

    government = "government"
    government_agency = "government_agency"
    national_news_agency = "national_news_agency"
    public_broadcaster = "public_broadcaster"
    independent_media = "independent_media"
    business_media = "business_media"
    international_wire = "international_wire"
    international_media = "international_media"
    research_institution = "research_institution"
    financial_institution = "financial_institution"
    social_signal = "social_signal"
    telegram_channel = "telegram_channel"


class SourceHealthStatus(str, enum.Enum):
    unknown = "unknown"
    healthy = "healthy"
    degraded = "degraded"
    failing = "failing"
    disabled = "disabled"


class VerificationStatus(str, enum.Enum):
    """Used for Telegram handles / sources that need manual confirmation."""

    verified = "verified"
    needs_verification = "needs_verification"
    unverified = "unverified"


class ArticleStatus(str, enum.Enum):
    raw = "raw"
    normalized = "normalized"
    duplicate = "duplicate"
    discarded = "discarded"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    ingest = "ingest"
    system = "system"


class ProcessingStatus(str, enum.Enum):
    """Intelligence pipeline state for an article.

    Flow: pending -> relevance_scored -> analyzed -> embedded -> clustered.
    Off-ramps: skipped_irrelevant (below relevance threshold), failed (will be
    retried), dead_letter (exceeded max attempts).
    """

    pending = "pending"
    relevance_scored = "relevance_scored"
    analyzed = "analyzed"
    embedded = "embedded"
    clustered = "clustered"
    skipped_irrelevant = "skipped_irrelevant"
    failed = "failed"
    dead_letter = "dead_letter"


class RelevanceDecision(str, enum.Enum):
    relevant = "relevant"
    borderline = "borderline"
    irrelevant = "irrelevant"


class ArticleRelationType(str, enum.Enum):
    """How an article relates to the event it is linked to."""

    primary = "primary"
    duplicate = "duplicate"
    related = "related"
    follow_up = "follow_up"
    context = "context"


class EventStatus(str, enum.Enum):
    developing = "developing"
    confirmed = "confirmed"
    updated = "updated"
    dormant = "dormant"
    closed = "closed"


class EventTimelineType(str, enum.Enum):
    first_report = "first_report"
    source_confirmation = "source_confirmation"
    new_development = "new_development"
    correction = "correction"
