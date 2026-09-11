"""initial schema

Enables required extensions (pgvector + pgcrypto) and creates all Phase 1
tables, enums, and indexes for the ETHIOTIMES news intelligence engine.

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""
from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions required by the schema.
    #   - vector: future article embeddings (semantic clustering, Phase 2+)
    #   - pgcrypto: gen_random_uuid() server-side default for UUID PKs
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "audit_logs",
        sa.Column(
            "action",
            sa.Enum("create", "update", "delete", "ingest", "system", name="audit_action"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Append-only audit trail of mutations and system actions.",
    )
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)

    op.create_table(
        "news_events",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("slug", sa.String(length=512), nullable=True),
        sa.Column("categories", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("significance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("article_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Clustered real-world events aggregating multiple articles.",
    )
    op.create_index(op.f("ix_news_events_slug"), "news_events", ["slug"], unique=False)

    op.create_table(
        "news_sources",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=1024), nullable=True),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("rss_url", sa.String(length=1024), nullable=True),
        sa.Column("api_url", sa.String(length=1024), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "government",
                "government_agency",
                "national_news_agency",
                "public_broadcaster",
                "independent_media",
                "business_media",
                "international_wire",
                "international_media",
                "research_institution",
                "financial_institution",
                "social_signal",
                "telegram_channel",
                name="source_type",
            ),
            nullable=False,
        ),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("trust_profile", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("coverage_categories", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("ethiopia_relevance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_primary_source", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum("verified", "needs_verification", "unverified", name="verification_status"),
            server_default="unverified",
            nullable=False,
        ),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("crawl_frequency_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "health_status",
            sa.Enum("unknown", "healthy", "degraded", "failing", "disabled", name="source_health_status"),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_articles_ingested", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_news_sources_slug"),
        comment="Registry of news sources ETHIOTIMES monitors and ingests.",
    )
    op.create_index(op.f("ix_news_sources_is_active"), "news_sources", ["is_active"], unique=False)
    op.create_index(op.f("ix_news_sources_slug"), "news_sources", ["slug"], unique=False)
    op.create_index(op.f("ix_news_sources_source_type"), "news_sources", ["source_type"], unique=False)

    op.create_table(
        "pipeline_jobs",
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "success", "failed", "skipped", name="job_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Execution records for Celery pipeline/ingestion tasks.",
    )
    op.create_index(op.f("ix_pipeline_jobs_celery_task_id"), "pipeline_jobs", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_pipeline_jobs_source_id"), "pipeline_jobs", ["source_id"], unique=False)
    op.create_index(op.f("ix_pipeline_jobs_task_name"), "pipeline_jobs", ["task_name"], unique=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Dashboard operators (Phase 1 scaffolding).",
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "articles",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("guid", sa.String(length=1024), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("raw_title", sa.Text(), nullable=True),
        sa.Column("raw_summary", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("categories", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("ethiopia_relevance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("relevance_keywords", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column(
            "status",
            sa.Enum("raw", "normalized", "duplicate", "discarded", name="article_status"),
            server_default="raw",
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url", name="uq_articles_canonical_url"),
        comment="Raw + normalized articles ingested from news sources.",
    )
    op.create_index(op.f("ix_articles_content_hash"), "articles", ["content_hash"], unique=False)
    op.create_index(op.f("ix_articles_guid"), "articles", ["guid"], unique=False)
    op.create_index(op.f("ix_articles_published_at"), "articles", ["published_at"], unique=False)
    op.create_index(op.f("ix_articles_source_id"), "articles", ["source_id"], unique=False)
    op.create_index("ix_articles_source_published", "articles", ["source_id", "published_at"], unique=False)
    op.create_index("ix_articles_status", "articles", ["status"], unique=False)

    op.create_table(
        "article_versions",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Historical versions of an article's content.",
    )
    op.create_index("ix_article_versions_article", "article_versions", ["article_id", "version_number"], unique=False)

    op.create_table(
        "event_articles",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("similarity_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "article_id", name="uq_event_article"),
        comment="Association between news_events and articles.",
    )


def downgrade() -> None:
    op.drop_table("event_articles")
    op.drop_index("ix_article_versions_article", table_name="article_versions")
    op.drop_table("article_versions")
    op.drop_index("ix_articles_status", table_name="articles")
    op.drop_index("ix_articles_source_published", table_name="articles")
    op.drop_index(op.f("ix_articles_source_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_published_at"), table_name="articles")
    op.drop_index(op.f("ix_articles_guid"), table_name="articles")
    op.drop_index(op.f("ix_articles_content_hash"), table_name="articles")
    op.drop_table("articles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_pipeline_jobs_task_name"), table_name="pipeline_jobs")
    op.drop_index(op.f("ix_pipeline_jobs_source_id"), table_name="pipeline_jobs")
    op.drop_index(op.f("ix_pipeline_jobs_celery_task_id"), table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
    op.drop_index(op.f("ix_news_sources_source_type"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_slug"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_is_active"), table_name="news_sources")
    op.drop_table("news_sources")
    op.drop_index(op.f("ix_news_events_slug"), table_name="news_events")
    op.drop_table("news_events")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    for enum_name in (
        "article_status",
        "job_status",
        "source_health_status",
        "verification_status",
        "source_type",
        "audit_action",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
