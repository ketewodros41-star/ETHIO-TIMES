"""Persist HTTP validators and content freshness for source polling."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_sources",
        sa.Column("refresh_tier", sa.String(length=16), server_default="standard", nullable=False),
    )
    op.add_column("news_sources", sa.Column("last_content_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("news_sources", sa.Column("http_etag", sa.String(length=512), nullable=True))
    op.add_column("news_sources", sa.Column("http_last_modified", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("news_sources", "http_last_modified")
    op.drop_column("news_sources", "http_etag")
    op.drop_column("news_sources", "last_content_at")
    op.drop_column("news_sources", "refresh_tier")
