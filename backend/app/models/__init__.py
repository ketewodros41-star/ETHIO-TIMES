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
    EventStatus,
    EventTimelineType,
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
    "NewsSource",
    "User",
    "ArticleRelationType",
    "ArticleStatus",
    "AuditAction",
    "EventStatus",
    "EventTimelineType",
    "JobStatus",
    "ProcessingStatus",
    "RelevanceDecision",
    "SourceHealthStatus",
    "SourceType",
    "VerificationStatus",
]
