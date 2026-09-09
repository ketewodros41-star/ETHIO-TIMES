"""ORM models. Importing this package registers all tables on `Base.metadata`."""

from app.db.base import Base
from app.models.article import (
    EMBEDDING_DIM,
    Article,
    ArticleAnalysis,
    ArticleVersion,
)
from app.models.audit import AuditLog, PipelineJob
from app.models.enums import (
    ArticleRelationType,
    ArticleStatus,
    AuditAction,
    ClaimType,
    ContradictionSeverity,
    EventStatus,
    EventTimelineType,
    EventVerificationStatus,
    EventVerifyStatus,
    JobStatus,
    ProcessingStatus,
    RelevanceDecision,
    SourceHealthStatus,
    SourceType,
    VerificationStatus,
)
from app.models.news_event import EventArticle, EventTimeline, NewsEvent
from app.models.news_source import NewsSource
from app.models.user import User
from app.models.verification import ClaimEvidence, Contradiction, EventClaim

__all__ = [
    "Base",
    "EMBEDDING_DIM",
    "Article",
    "ArticleAnalysis",
    "ArticleVersion",
    "AuditLog",
    "PipelineJob",
    "NewsEvent",
    "EventArticle",
    "EventTimeline",
    "EventClaim",
    "ClaimEvidence",
    "Contradiction",
    "NewsSource",
    "User",
    "ArticleRelationType",
    "ArticleStatus",
    "AuditAction",
    "ClaimType",
    "ContradictionSeverity",
    "EventStatus",
    "EventTimelineType",
    "EventVerificationStatus",
    "EventVerifyStatus",
    "JobStatus",
    "ProcessingStatus",
    "RelevanceDecision",
    "SourceHealthStatus",
    "SourceType",
    "VerificationStatus",
]
