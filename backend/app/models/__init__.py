"""ORM models. Importing this package registers all tables on `Base.metadata`."""

from app.db.base import Base
from app.models.article import EMBEDDING_DIM, Article, ArticleVersion
from app.models.audit import AuditLog, PipelineJob
from app.models.enums import (
    ArticleStatus,
    AuditAction,
    JobStatus,
    SourceHealthStatus,
    SourceType,
    VerificationStatus,
)
from app.models.news_event import EventArticle, NewsEvent
from app.models.news_source import NewsSource
from app.models.user import User

__all__ = [
    "Base",
    "EMBEDDING_DIM",
    "Article",
    "ArticleVersion",
    "AuditLog",
    "PipelineJob",
    "NewsEvent",
    "EventArticle",
    "NewsSource",
    "User",
    "ArticleStatus",
    "AuditAction",
    "JobStatus",
    "SourceHealthStatus",
    "SourceType",
    "VerificationStatus",
]
