"""Add content_filters to telegram_publishing_settings.

Adds a JSONB column `content_filters` that stores per-bucket topic/category
and keyword filter configuration used by plan_telegram_posts().
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_DEFAULT_CONTENT_FILTERS = """{
  "ethiopia": {
    "allowed_categories": [],
    "blocked_categories": [],
    "allowed_keywords": [],
    "blocked_keywords": ["sponsored", "advertisement", "advertorial", "press release", "partner content", "ad feature", "promoted"]
  },
  "international": {
    "allowed_categories": [],
    "blocked_categories": [],
    "allowed_keywords": [],
    "blocked_keywords": ["sponsored", "advertisement", "advertorial", "press release", "partner content", "ad feature", "promoted"]
  }
}"""


def upgrade() -> None:
    op.add_column(
        "telegram_publishing_settings",
        sa.Column(
            "content_filters",
            postgresql.JSONB(),
            server_default=sa.text(f"'{_DEFAULT_CONTENT_FILTERS}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("telegram_publishing_settings", "content_filters")
