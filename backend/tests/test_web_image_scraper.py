"""Unit tests for WebImageScraper and story-relevant photo discovery."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.article import Article
from app.models.news_event import EventArticle, NewsEvent
from app.models.news_source import NewsSource
from app.models.enums import SourceType
from app.schemas.social_post import PhotoCandidate
from app.services.social.web_image_scraper import WebImageScraper


@pytest.fixture
def sample_event() -> NewsEvent:
    event = NewsEvent(
        id=uuid.uuid4(),
        title="Commercial Bank of Ethiopia Launches New Digital Banking System",
        summary="CBE introduces advanced mobile banking technology across branches in Addis Ababa.",
        primary_category="economy",
        primary_region="Addis Ababa",
    )
    # Mock linked article with editorial photo
    art = Article(
        id=uuid.uuid4(),
        title="CBE Unveils Digital Platform",
        image_url="https://combanketh.et/uploads/cbe_launch.jpg",
    )
    art.source = NewsSource(
        name="The Reporter Ethiopia",
        slug="the-reporter",
        source_type=SourceType.independent_media,
    )
    link = EventArticle(event_id=event.id, article_id=art.id)
    link.article = art
    event.article_links = [link]
    return event


def test_web_image_scraper_extracts_article_photos(sample_event: NewsEvent):
    scraper = WebImageScraper(text_provider=None)
    candidates = scraper._extract_article_photos(sample_event)
    assert len(candidates) == 1
    assert candidates[0].image_url == "https://combanketh.et/uploads/cbe_launch.jpg"
    assert candidates[0].source == "article_source"
    assert candidates[0].photographer == "The Reporter Ethiopia"


def test_web_image_scraper_heuristic_queries(sample_event: NewsEvent):
    scraper = WebImageScraper(text_provider=None)
    queries = scraper._generate_visual_queries(sample_event)
    assert len(queries) >= 1
    assert any("Commercial" in q for q in queries)


def test_web_image_scraper_llm_queries(sample_event: NewsEvent):
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_res = MagicMock()
    mock_res.text = '["Commercial Bank of Ethiopia press conference", "CBE headquarters Addis Ababa"]'
    mock_provider.generate_text.return_value = mock_res

    scraper = WebImageScraper(text_provider=mock_provider)
    queries = scraper._generate_visual_queries(sample_event)
    assert len(queries) == 2
    assert queries[0] == "Commercial Bank of Ethiopia press conference"


@patch.object(WebImageScraper, "_search_bing_photos")
def test_web_image_scraper_search_candidates(mock_bing, sample_event: NewsEvent):
    mock_bing.return_value = [
        PhotoCandidate(
            id="bing-1",
            title="CBE Press Briefing",
            thumb_url="https://example.com/thumb.jpg",
            image_url="https://example.com/highres.jpg",
            source="web_search",
            photographer="addisstandard.com",
            description="Press briefing photo",
        )
    ]
    scraper = WebImageScraper(text_provider=None)
    results = scraper.search_candidates(sample_event, max_pool=6)

    # First should be the authentic article photo, second should be the web search photo
    assert len(results) == 2
    assert results[0].source == "article_source"
    assert results[1].source == "web_search"
    assert results[1].photographer == "addisstandard.com"
