"""phase 3 verification schema

Adds claim extraction, evidence mapping, contradiction detection, and event
verification fields. PostgreSQL enum ``event_verification_status`` is named
distinctly from the existing source-handle ``verification_status``.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUMS = {
    "event_verification_status": postgresql.ENUM(
        "unverified",
        "developing",
        "partially_confirmed",
        "confirmed",
        "contradicted",
        name="event_verification_status",
    ),
    "event_verify_status": postgresql.ENUM(
        "pending",
        "verifying",
        "verified",
        "failed",
        "dead_letter",
        name="event_verify_status",
    ),
    "claim_type": postgresql.ENUM(
        "financial",
        "statistical",
        "political",
        "policy",
        "casualty",
        "geographic",
        "timeline",
        "announcement",
        name="claim_type",
    ),
    "contradiction_severity": postgresql.ENUM(
        "low", "medium", "high", "critical", name="contradiction_severity"
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in _ENUMS.values():
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "event_claims",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column(
            "claim_type",
            postgresql.ENUM(name="claim_type", create_type=False),
            nullable=False,
        ),
        sa.Column("normalized_value", sa.String(length=255), nullable=True),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("canonical_key", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("is_major", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Structured claims extracted from articles covering an event.",
    )
    op.create_index(op.f("ix_event_claims_event_id"), "event_claims", ["event_id"])
    op.create_index(op.f("ix_event_claims_article_id"), "event_claims", ["article_id"])
    op.create_index(op.f("ix_event_claims_claim_type"), "event_claims", ["claim_type"])
    op.create_index(
        op.f("ix_event_claims_canonical_key"), "event_claims", ["canonical_key"]
    )

    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["event_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "claim_id", "article_id", name="uq_claim_evidence_claim_article"
        ),
        comment="Source excerpts/URLs backing a claim.",
    )
    op.create_index(op.f("ix_claim_evidence_claim_id"), "claim_evidence", ["claim_id"])
    op.create_index(
        op.f("ix_claim_evidence_article_id"), "claim_evidence", ["article_id"]
    )
    op.create_index(op.f("ix_claim_evidence_source_id"), "claim_evidence", ["source_id"])

    op.create_table(
        "contradictions",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("claim_a_id", sa.UUID(), nullable=False),
        sa.Column("claim_b_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(name="contradiction_severity", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_a_id"], ["event_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_b_id"], ["event_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Conflicting claims across sources covering the same event.",
    )
    op.create_index(op.f("ix_contradictions_event_id"), "contradictions", ["event_id"])
    op.create_index(
        op.f("ix_contradictions_claim_a_id"), "contradictions", ["claim_a_id"]
    )
    op.create_index(
        op.f("ix_contradictions_claim_b_id"), "contradictions", ["claim_b_id"]
    )
    op.create_index(op.f("ix_contradictions_severity"), "contradictions", ["severity"])

    # --- news_events: verification surface --- #
    op.add_column(
        "news_events",
        sa.Column("verification_score", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "event_verification_status",
            postgresql.ENUM(name="event_verification_status", create_type=False),
            server_default="unverified",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "verification_explanation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "primary_source_available",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "cited_institutions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "discovered_primary_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "review_required", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "review_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "auto_publish_eligible",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "verification_processing_status",
            postgresql.ENUM(name="event_verify_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "verification_attempts", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "news_events", sa.Column("last_verification_error", sa.Text(), nullable=True)
    )
    op.add_column(
        "news_events",
        sa.Column("verification_lock_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "news_events",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_news_events_event_verification_status"),
        "news_events",
        ["event_verification_status"],
    )
    op.create_index(
        op.f("ix_news_events_primary_source_available"),
        "news_events",
        ["primary_source_available"],
    )
    op.create_index(
        op.f("ix_news_events_review_required"), "news_events", ["review_required"]
    )
    op.create_index(
        op.f("ix_news_events_verification_processing_status"),
        "news_events",
        ["verification_processing_status"],
    )

    op.add_column("pipeline_jobs", sa.Column("event_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_pipeline_jobs_event_id"), "pipeline_jobs", ["event_id"])
    op.create_foreign_key(
        "fk_pipeline_jobs_event_id",
        "pipeline_jobs",
        "news_events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_pipeline_jobs_event_id", "pipeline_jobs", type_="foreignkey")
    op.drop_index(op.f("ix_pipeline_jobs_event_id"), table_name="pipeline_jobs")
    op.drop_column("pipeline_jobs", "event_id")

    op.drop_index(
        op.f("ix_news_events_verification_processing_status"), table_name="news_events"
    )
    op.drop_index(op.f("ix_news_events_review_required"), table_name="news_events")
    op.drop_index(
        op.f("ix_news_events_primary_source_available"), table_name="news_events"
    )
    op.drop_index(
        op.f("ix_news_events_event_verification_status"), table_name="news_events"
    )
    for col in (
        "verified_at",
        "verification_lock_until",
        "last_verification_error",
        "verification_attempts",
        "verification_processing_status",
        "auto_publish_eligible",
        "review_reasons",
        "review_required",
        "discovered_primary_source_ids",
        "cited_institutions",
        "primary_source_available",
        "verification_explanation",
        "event_verification_status",
        "verification_score",
    ):
        op.drop_column("news_events", col)

    op.drop_index(op.f("ix_contradictions_severity"), table_name="contradictions")
    op.drop_index(op.f("ix_contradictions_claim_b_id"), table_name="contradictions")
    op.drop_index(op.f("ix_contradictions_claim_a_id"), table_name="contradictions")
    op.drop_index(op.f("ix_contradictions_event_id"), table_name="contradictions")
    op.drop_table("contradictions")

    op.drop_index(op.f("ix_claim_evidence_source_id"), table_name="claim_evidence")
    op.drop_index(op.f("ix_claim_evidence_article_id"), table_name="claim_evidence")
    op.drop_index(op.f("ix_claim_evidence_claim_id"), table_name="claim_evidence")
    op.drop_table("claim_evidence")

    op.drop_index(op.f("ix_event_claims_canonical_key"), table_name="event_claims")
    op.drop_index(op.f("ix_event_claims_claim_type"), table_name="event_claims")
    op.drop_index(op.f("ix_event_claims_article_id"), table_name="event_claims")
    op.drop_index(op.f("ix_event_claims_event_id"), table_name="event_claims")
    op.drop_table("event_claims")

    for enum_name in (
        "contradiction_severity",
        "claim_type",
        "event_verify_status",
        "event_verification_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
