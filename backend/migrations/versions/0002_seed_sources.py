"""seed Ethiopian news source registry

Inserts the Phase 1 seed set of Ethiopian-focused sources. Idempotent: rows are
matched by unique `slug` and skipped if already present.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.data.sources_seed import SEED_SOURCES

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INSERT_SQL = sa.text(
    """
    INSERT INTO news_sources (
        name, slug, description, website, base_url, rss_url, api_url,
        telegram_username, telegram_url, source_type, country, language,
        trust_profile, coverage_categories, ethiopia_relevance_score,
        is_primary_source, verification_status, verification_notes,
        is_active, crawl_frequency_minutes
    ) VALUES (
        :name, :slug, :description, :website, :base_url, :rss_url, :api_url,
        :telegram_username, :telegram_url, CAST(:source_type AS source_type),
        :country, :language, CAST(:trust_profile AS jsonb),
        CAST(:coverage_categories AS jsonb), :ethiopia_relevance_score,
        :is_primary_source, CAST(:verification_status AS verification_status),
        :verification_notes, :is_active, :crawl_frequency_minutes
    )
    ON CONFLICT (slug) DO NOTHING
    """
)


def _params(src: dict) -> dict:
    return {
        "name": src["name"],
        "slug": src["slug"],
        "description": src.get("description"),
        "website": src.get("website"),
        "base_url": src.get("base_url"),
        "rss_url": src.get("rss_url"),
        "api_url": src.get("api_url"),
        "telegram_username": src.get("telegram_username"),
        "telegram_url": src.get("telegram_url"),
        "source_type": src["source_type"],
        "country": src.get("country", "ET"),
        "language": src.get("language", "en"),
        "trust_profile": json.dumps(src.get("trust_profile", {})),
        "coverage_categories": json.dumps(src.get("coverage_categories", [])),
        "ethiopia_relevance_score": src.get("ethiopia_relevance_score", 0.0),
        "is_primary_source": src.get("is_primary_source", False),
        "verification_status": src.get("verification_status", "unverified"),
        "verification_notes": src.get("verification_notes"),
        "is_active": src.get("is_active", True),
        "crawl_frequency_minutes": src.get("crawl_frequency_minutes", 30),
    }


def upgrade() -> None:
    conn = op.get_bind()
    for src in SEED_SOURCES:
        conn.execute(_INSERT_SQL, _params(src))


def downgrade() -> None:
    conn = op.get_bind()
    slugs = [s["slug"] for s in SEED_SOURCES]
    conn.execute(
        sa.text("DELETE FROM news_sources WHERE slug = ANY(:slugs)"),
        {"slugs": slugs},
    )
