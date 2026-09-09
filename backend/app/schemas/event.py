"""Pydantic schemas for news events (Phase 2 + Phase 3 verification)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ArticleRelationType,
    ClaimType,
    ContradictionSeverity,
    EventStatus,
    EventTimelineType,
    EventVerificationStatus,
    EventVerifyStatus,
    ProcessingStatus,
    RelevanceDecision,
)
from app.models.news_event import EventArticle, EventTimeline, NewsEvent
from app.models.verification import ClaimEvidence, Contradiction, EventClaim


class SourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str


class ArticleSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    summary: str | None
    url: str | None
    published_at: datetime | None
    detected_language: str | None
    importance_score: float
    relevance_score: int | None
    relevance_decision: RelevanceDecision | None
    processing_status: ProcessingStatus
    category: str | None
    source: SourceRef | None


class EventArticleRead(BaseModel):
    relation_type: ArticleRelationType
    similarity_score: float
    confidence: float
    is_primary: bool
    article: ArticleSummary


class EventTimelineRead(BaseModel):
    id: uuid.UUID
    entry_type: EventTimelineType
    occurred_at: datetime
    title: str | None
    detail: dict
    article_id: uuid.UUID | None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    summary: str | None
    slug: str | None
    status: EventStatus
    primary_category: str | None
    primary_region: str | None
    categories: list[str]
    key_entities: list[str]
    significance_score: float
    cluster_confidence: float
    article_count: int
    source_count: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    verification_score: int = 0
    event_verification_status: EventVerificationStatus = EventVerificationStatus.unverified
    primary_source_available: bool = False
    review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    auto_publish_eligible: bool = False
    verification_processing_status: EventVerifyStatus = EventVerifyStatus.pending
    verified_at: datetime | None = None


class ClaimEvidenceRead(BaseModel):
    article_id: uuid.UUID
    source_id: uuid.UUID | None
    excerpt: str
    url: str | None


class EventClaimRead(BaseModel):
    id: uuid.UUID
    claim_text: str
    claim_type: ClaimType
    normalized_value: str | None
    entities: list[str]
    canonical_key: str | None
    confidence: float
    is_major: bool
    evidence: list[ClaimEvidenceRead]


class ContradictionRead(BaseModel):
    id: uuid.UUID
    claim_a_id: uuid.UUID
    claim_b_id: uuid.UUID
    description: str
    severity: ContradictionSeverity
    details: dict


class EventDetail(EventRead):
    articles: list[EventArticleRead]
    timeline: list[EventTimelineRead]
    claims: list[EventClaimRead]
    contradictions: list[ContradictionRead]
    verification_explanation: dict
    cited_institutions: list[str]
    discovered_primary_source_ids: list[str]


# --------------------------------------------------------------------------- #
# Serializers (build from ORM objects with loaded relationships)
# --------------------------------------------------------------------------- #
def _article_summary(article) -> ArticleSummary:  # noqa: ANN001
    return ArticleSummary(
        id=article.id,
        title=article.title,
        summary=article.summary,
        url=article.url,
        published_at=article.published_at,
        detected_language=article.detected_language,
        importance_score=article.importance_score,
        relevance_score=article.relevance_score,
        relevance_decision=article.relevance_decision,
        processing_status=article.processing_status,
        category=(article.analysis.category if article.analysis else None),
        source=SourceRef.model_validate(article.source) if article.source else None,
    )


def to_event_article(link: EventArticle) -> EventArticleRead:
    return EventArticleRead(
        relation_type=link.relation_type,
        similarity_score=link.similarity_score,
        confidence=link.confidence,
        is_primary=link.is_primary,
        article=_article_summary(link.article),
    )


def to_timeline(entry: EventTimeline) -> EventTimelineRead:
    return EventTimelineRead(
        id=entry.id,
        entry_type=entry.entry_type,
        occurred_at=entry.occurred_at,
        title=entry.title,
        detail=entry.detail or {},
        article_id=entry.article_id,
    )


def to_event_detail(event: NewsEvent) -> EventDetail:
    base = EventRead.model_validate(event).model_dump()
    # Primary first, then by similarity desc.
    links = sorted(
        event.article_links,
        key=lambda x: (not x.is_primary, -x.similarity_score),
    )
    timeline = sorted(event.timeline, key=lambda x: x.occurred_at)
    claims = sorted(
        event.claims,
        key=lambda c: (not c.is_major, -c.confidence, c.created_at),
    )
    contradictions = sorted(
        event.contradictions,
        key=lambda c: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(c.severity.value, 9),
            c.created_at,
        ),
    )
    return EventDetail(
        **base,
        articles=[to_event_article(link) for link in links],
        timeline=[to_timeline(entry) for entry in timeline],
        claims=[_claim_read(c) for c in claims],
        contradictions=[_contradiction_read(c) for c in contradictions],
        verification_explanation=event.verification_explanation or {},
        cited_institutions=list(event.cited_institutions or []),
        discovered_primary_source_ids=[
            str(x) for x in (event.discovered_primary_source_ids or [])
        ],
    )


def _claim_read(claim: EventClaim) -> EventClaimRead:
    return EventClaimRead(
        id=claim.id,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        normalized_value=claim.normalized_value,
        entities=list(claim.entities or []),
        canonical_key=claim.canonical_key,
        confidence=claim.confidence,
        is_major=claim.is_major,
        evidence=[_evidence_read(e) for e in claim.evidence],
    )


def _evidence_read(row: ClaimEvidence) -> ClaimEvidenceRead:
    return ClaimEvidenceRead(
        article_id=row.article_id,
        source_id=row.source_id,
        excerpt=row.excerpt,
        url=row.url,
    )


def _contradiction_read(row: Contradiction) -> ContradictionRead:
    return ContradictionRead(
        id=row.id,
        claim_a_id=row.claim_a_id,
        claim_b_id=row.claim_b_id,
        description=row.description,
        severity=row.severity,
        details=row.details or {},
    )
