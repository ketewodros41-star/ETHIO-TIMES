"""Add isolated Telegram publishing policy and delivery ledger."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_publishing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dry_run", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("channel_username", sa.String(length=128), server_default="@Ethiopantimes", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Africa/Addis_Ababa", nullable=False),
        sa.Column("posts_per_day", sa.Integer(), server_default="5", nullable=False),
        sa.Column("ethiopia_posts_per_day", sa.Integer(), server_default="3", nullable=False),
        sa.Column("international_posts_per_day", sa.Integer(), server_default="2", nullable=False),
        sa.Column("posting_hours", postgresql.JSONB(), server_default=sa.text("'[8, 11, 14, 17, 20]'::jsonb"), nullable=False),
        sa.Column("highlight_color", sa.String(length=16), server_default="#00F0FF", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "telegram_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_bucket", sa.String(length=24), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("source_attribution", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.String(length=2048), nullable=True),
        sa.Column("photo_credit", sa.String(length=512), nullable=True),
        sa.Column("highlight_words", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("highlight_color", sa.String(length=16), server_default="#00F0FF", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="scheduled", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.String(length=128), nullable=True),
        sa.Column("dry_run", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("policy_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["news_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "content_bucket", name="uq_telegram_posts_event_bucket"),
        sa.UniqueConstraint("telegram_message_id"),
    )
    op.create_index("ix_telegram_posts_event_id", "telegram_posts", ["event_id"])
    op.create_index("ix_telegram_posts_status", "telegram_posts", ["status"])
    op.create_index("ix_telegram_posts_scheduled_at", "telegram_posts", ["scheduled_at"])


def downgrade() -> None:
    op.drop_table("telegram_posts")
    op.drop_table("telegram_publishing_settings")
