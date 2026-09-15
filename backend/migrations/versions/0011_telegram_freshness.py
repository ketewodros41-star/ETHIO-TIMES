"""Add telegram freshness controls, event_seen_at, and first_article_published_at.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add freshness_hours and bypass_freshness_for_breaking to telegram_publishing_settings
    op.add_column(
        "telegram_publishing_settings",
        sa.Column(
            "freshness_hours",
            sa.Integer(),
            server_default=sa.text("36"),
            nullable=False,
        ),
    )
    op.add_column(
        "telegram_publishing_settings",
        sa.Column(
            "bypass_freshness_for_breaking",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    # 2. Add event_seen_at to telegram_posts for audit trail
    op.add_column(
        "telegram_posts",
        sa.Column(
            "event_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 3. Add first_article_published_at to news_events for accurate chronological sorting
    op.add_column(
        "news_events",
        sa.Column(
            "first_article_published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_news_events_first_article_published_at",
        "news_events",
        ["first_article_published_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_news_events_first_article_published_at", table_name="news_events")
    op.drop_column("news_events", "first_article_published_at")
    op.drop_column("telegram_posts", "event_seen_at")
    op.drop_column("telegram_publishing_settings", "bypass_freshness_for_breaking")
    op.drop_column("telegram_publishing_settings", "freshness_hours")
