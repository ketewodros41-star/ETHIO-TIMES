"""phase 2 intelligence schema

Adds the intelligence pipeline surface: per-article processing state, relevance
and analysis fields, the `article_analysis` detail table, embedding metadata,
event lifecycle fields, typed event/article relations, the `event_timeline`
table, and HNSW cosine indexes for vector nearest-neighbor search.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09
"""
from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum types are created explicitly up front. `add_column` (unlike `create_table`)
# does not auto-create the referenced PG enum type, so we create them here and
# pass create_type=False on every column definition below.
_ENUMS = {
    "processing_status": postgresql.ENUM(
        "pending",
        "relevance_scored",
        "analyzed",
        "embedded",
        "clustered",
        "skipped_irrelevant",
        "failed",
        "dead_letter",
        name="processing_status",
    ),
    "relevance_decision": postgresql.ENUM(
        "relevant", "borderline", "irrelevant", name="relevance_decision"
    ),
    "article_relation_type": postgresql.ENUM(
        "primary", "duplicate", "related", "follow_up", "context",
        name="article_relation_type",
    ),
    "event_status": postgresql.ENUM(
        "developing", "confirmed", "updated", "dormant", "closed", name="event_status"
    ),
    "event_timeline_type": postgresql.ENUM(
        "first_report", "source_confirmation", "new_development", "correction",
        name="event_timeline_type",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in _ENUMS.values():
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "article_analysis",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("language_name", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("subcategory", sa.String(length=128), nullable=True),
        sa.Column("importance", sa.Integer(), server_default="50", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("dates", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("money", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("statistics", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("entity_names", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", name="uq_article_analysis_article"),
        comment="Structured NLP/AI analysis for an article.",
    )
    op.create_index(op.f("ix_article_analysis_category"), "article_analysis", ["category"], unique=False)

    op.create_table(
        "event_timeline",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column(
            "entry_type",
            postgresql.ENUM(name="event_timeline_type", create_type=False),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Notable moments in the lifecycle of a news event.",
    )
    op.create_index(op.f("ix_event_timeline_event_id"), "event_timeline", ["event_id"], unique=False)

    # --- articles: pipeline state + relevance + analysis + embedding meta --- #
    op.add_column(
        "articles",
        sa.Column(
            "processing_status",
            postgresql.ENUM(name="processing_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("articles", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("articles", sa.Column("processing_locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("articles", sa.Column("relevance_score", sa.Integer(), nullable=True))
    op.add_column(
        "articles",
        sa.Column(
            "relevance_decision",
            postgresql.ENUM(name="relevance_decision", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("articles", sa.Column("is_ethiopia_related", sa.Boolean(), nullable=True))
    op.add_column("articles", sa.Column("relevance_reason", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("primary_region", sa.String(length=128), nullable=True))
    op.add_column("articles", sa.Column("relevance_scored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("articles", sa.Column("detected_language", sa.String(length=16), nullable=True))
    op.add_column("articles", sa.Column("importance_score", sa.Float(), server_default="0", nullable=False))
    op.add_column("articles", sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("articles", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("articles", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_articles_processing_status"), "articles", ["processing_status"], unique=False)
    op.create_index(op.f("ix_articles_relevance_decision"), "articles", ["relevance_decision"], unique=False)

    # --- event_articles: typed relation + confidence --- #
    op.add_column(
        "event_articles",
        sa.Column(
            "relation_type",
            postgresql.ENUM(name="article_relation_type", create_type=False),
            server_default="primary",
            nullable=False,
        ),
    )
    op.add_column("event_articles", sa.Column("confidence", sa.Float(), server_default="0", nullable=False))
    op.create_index(op.f("ix_event_articles_article_id"), "event_articles", ["article_id"], unique=False)
    op.create_index(op.f("ix_event_articles_event_id"), "event_articles", ["event_id"], unique=False)

    # --- news_events: lifecycle + centroid --- #
    op.add_column(
        "news_events",
        sa.Column(
            "status",
            postgresql.ENUM(name="event_status", create_type=False),
            server_default="developing",
            nullable=False,
        ),
    )
    op.add_column("news_events", sa.Column("primary_category", sa.String(length=128), nullable=True))
    op.add_column("news_events", sa.Column("primary_region", sa.String(length=128), nullable=True))
    op.add_column("news_events", sa.Column("key_entities", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False))
    op.add_column("news_events", sa.Column("cluster_confidence", sa.Float(), server_default="0", nullable=False))
    op.add_column("news_events", sa.Column("source_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("news_events", sa.Column("centroid_embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True))
    op.create_index(op.f("ix_news_events_status"), "news_events", ["status"], unique=False)

    # --- HNSW cosine indexes for nearest-neighbor search --- #
    # Vectors are L2-normalized in the provider, so cosine distance is used.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_embedding_hnsw "
        "ON articles USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_news_events_centroid_hnsw "
        "ON news_events USING hnsw (centroid_embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_news_events_centroid_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_articles_embedding_hnsw")

    op.drop_index(op.f("ix_news_events_status"), table_name="news_events")
    op.drop_column("news_events", "centroid_embedding")
    op.drop_column("news_events", "source_count")
    op.drop_column("news_events", "cluster_confidence")
    op.drop_column("news_events", "key_entities")
    op.drop_column("news_events", "primary_region")
    op.drop_column("news_events", "primary_category")
    op.drop_column("news_events", "status")

    op.drop_index(op.f("ix_event_articles_event_id"), table_name="event_articles")
    op.drop_index(op.f("ix_event_articles_article_id"), table_name="event_articles")
    op.drop_column("event_articles", "confidence")
    op.drop_column("event_articles", "relation_type")

    op.drop_index(op.f("ix_articles_relevance_decision"), table_name="articles")
    op.drop_index(op.f("ix_articles_processing_status"), table_name="articles")
    for col in (
        "embedded_at",
        "embedding_model",
        "analyzed_at",
        "importance_score",
        "detected_language",
        "relevance_scored_at",
        "primary_region",
        "relevance_reason",
        "is_ethiopia_related",
        "relevance_decision",
        "relevance_score",
        "processing_locked_at",
        "processing_attempts",
        "processing_error",
        "processing_status",
    ):
        op.drop_column("articles", col)

    op.drop_index(op.f("ix_event_timeline_event_id"), table_name="event_timeline")
    op.drop_table("event_timeline")
    op.drop_index(op.f("ix_article_analysis_category"), table_name="article_analysis")
    op.drop_table("article_analysis")

    for enum_name in (
        "event_timeline_type",
        "event_status",
        "article_relation_type",
        "relevance_decision",
        "processing_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
