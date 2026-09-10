"""Tests for Supabase free tier storage optimization and pruning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from unittest.mock import MagicMock

from app.models.enums import SourceType
from app.models.news_source import NewsSource
from app.pipelines.adapters.base import FetchedItem
from app.services.ingestion_service import IngestionService


def test_build_article_truncation_and_deduplication():
    source = NewsSource(
        id=uuid.uuid4(),
        name="Test News",
        slug="test-news",
        source_type=SourceType.independent_media,
        language="en",
    )
    service = IngestionService(MagicMock())

    long_content = "Word " * 1500  # ~7500 characters
    long_summary = "Summary " * 300  # ~2400 characters

    item = FetchedItem(
        canonical_url="https://example.com/story-1",
        url="https://example.com/story-1",
        guid="story-1",
        title="Breaking News in Ethiopia",
        summary=long_summary,
        content=long_content,
        author="Reporter",
        language="en",
        categories=["politics"],
        image_url="https://example.com/photo.jpg",
        published_at=datetime.now(UTC),
        raw_payload={"id": "story-1", "link": "https://example.com/story-1", "extra_html": "<p>huge blob</p>"},
    )

    article = service._build_article(source, item)

    # Verify content and summary are sanitized and truncated
    assert article.content is not None
    assert len(article.content) <= 3000
    assert article.summary is not None
    assert len(article.summary) <= 1000

    # Verify raw duplicates are eliminated to conserve Supabase 500MB DB storage
    assert article.raw_content is None
    assert article.raw_summary is None

    # Verify raw_payload does not store arbitrary large blobs
    assert "extra_html" not in article.raw_payload
    assert article.raw_payload.get("id") == "story-1"


def test_prune_stale_storage_logic():
    from app.api.routes.pipeline import prune_stale_storage

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.rowcount = 42
    mock_session.execute.return_value = mock_result

    res = prune_stale_storage(
        session=mock_session,
        jobs_max_age_days=7,
        articles_max_age_days=60,
    )

    assert res["deleted_jobs"] == 42
    assert res["deleted_articles"] == 42
    assert "42 old job logs" in res["message"]
    mock_session.commit.assert_called_once()

