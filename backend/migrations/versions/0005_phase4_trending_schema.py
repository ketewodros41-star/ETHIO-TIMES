"""phase 4 trending schema

Adds trend scoring fields on ``news_events`` and the ``event_velocity_metrics``
table used by the trend intelligence pipeline.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUMS = {
    "trend_status": postgresql.ENUM(
        "low",
        "emerging",
        "trending",
        "high_priority",
        "breaking",
        name="trend_status",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in _ENUMS.values():
        enum_type.create(bind, checkfirst=True)

    op.add_column(
        "news_events",
        sa.Column("trend_score", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "trend_status",
            postgresql.ENUM(name="trend_status", create_type=False),
            server_default="low",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "trend_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "editorial_importance", sa.Float(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "news_events",
        sa.Column(
            "breaking_candidate", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "news_events",
        sa.Column("trend_scored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_news_events_trend_status"), "news_events", ["trend_status"])
    op.create_index(
        op.f("ix_news_events_breaking_candidate"), "news_events", ["breaking_candidate"]
    )
    op.create_index(op.f("ix_news_events_trend_score"), "news_events", ["trend_score"])

    op.create_table(
        "event_velocity_metrics",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("article_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unique_source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("growth_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("articles_per_hour", sa.Float(), server_default="0", nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "window_hours", name="uq_event_velocity_window"),
        comment="Per-window article/source velocity snapshots for news events.",
    )
    op.create_index(
        op.f("ix_event_velocity_metrics_event_id"),
        "event_velocity_metrics",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_event_velocity_metrics_event_id"), table_name="event_velocity_metrics"
    )
    op.drop_table("event_velocity_metrics")

    op.drop_index(op.f("ix_news_events_trend_score"), table_name="news_events")
    op.drop_index(op.f("ix_news_events_breaking_candidate"), table_name="news_events")
    op.drop_index(op.f("ix_news_events_trend_status"), table_name="news_events")
    for col in (
        "trend_scored_at",
        "breaking_candidate",
        "editorial_importance",
        "trend_breakdown",
        "trend_status",
        "trend_score",
    ):
        op.drop_column("news_events", col)

    op.execute("DROP TYPE IF EXISTS trend_status")
