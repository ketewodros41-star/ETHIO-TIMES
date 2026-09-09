"""`articles` and `article_versions` — ingested content, raw + normalized."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ArticleStatus

# Dimensionality reserved for future embeddings (e.g. text-embedding models).
EMBEDDING_DIM = 1536


class Article(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_articles_canonical_url"),
        Index("ix_articles_source_published", "source_id", "published_at"),
        Index("ix_articles_status", "status"),
        {"comment": "Raw + normalized articles ingested from news sources."},
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ---- Identity / dedup ----
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    guid: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    # ---- Raw fields (as received from source) ----
    raw_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # ---- Normalized fields ----
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # ---- Relevance (keyword stub in Phase 1; Gemini filter in Phase 2) ----
    ethiopia_relevance_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    relevance_keywords: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # ---- Lifecycle ----
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus, name="article_status", native_enum=True),
        nullable=False,
        default=ArticleStatus.raw,
        server_default=ArticleStatus.raw.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Future embeddings (nullable; populated in a later phase) ----
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    # ---- Relationships ----
    source: Mapped[NewsSource] = relationship(  # noqa: F821
        back_populates="articles"
    )
    versions: Mapped[list[ArticleVersion]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    event_links: Mapped[list[EventArticle]] = relationship(  # noqa: F821
        back_populates="article", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Article {self.id} {self.title!r}>"


class ArticleVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable snapshot of an article's content at a point in time.

    Enables change tracking when a source edits a story after publication.
    """

    __tablename__ = "article_versions"
    __table_args__ = (
        Index("ix_article_versions_article", "article_id", "version_number"),
        {"comment": "Historical versions of an article's content."},
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    article: Mapped[Article] = relationship(back_populates="versions")
