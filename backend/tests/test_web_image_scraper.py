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
    person, queries = scraper._analyze_entities_and_queries(sample_event)
    assert person is None
    assert len(queries) >= 1
    assert any("Commercial Bank" in q for q in queries)


def test_web_image_scraper_person_detection():
    event = NewsEvent(
        id=uuid.uuid4(),
        title="ጠቅላይ ሚኒስትር ዐቢይ አሕመድ አዲስ ንግግር አደረጉ",
        summary="ጠቅላይ ሚኒስትሩ በፓርላማ ተገኝተዋል",
    )
    scraper = WebImageScraper(text_provider=None)
    person, queries = scraper._analyze_entities_and_queries(event)
    assert person == "Abiy Ahmed"
    assert any("Abiy Ahmed" in q for q in queries)


def test_web_image_scraper_llm_queries(sample_event: NewsEvent):
    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_res = MagicMock()
    mock_res.text = '{"main_person": null, "queries": ["Commercial Bank of Ethiopia press conference", "CBE headquarters"]}'
    mock_provider.generate_text.return_value = mock_res

    scraper = WebImageScraper(text_provider=mock_provider)
    person, queries = scraper._analyze_entities_and_queries(sample_event)
    assert person is None
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
    assert len(results) >= 1
    assert results[0].source == "article_source"


def test_search_openverse_parsing():
    scraper = WebImageScraper(text_provider=None)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "url": "https://live.staticflickr.com/1234/test.jpg",
                "thumbnail": "https://live.staticflickr.com/1234/thumb.jpg",
                "title": "Prime Minister Abiy Ahmed at African Union Summit",
                "creator": "Paul Kagame",
                "source": "flickr",
            },
            {
                "url": "https://example.com/bad.svg",  # should be excluded
                "thumbnail": "https://example.com/bad_thumb.jpg",
                "title": "Flag of Ethiopia",
                "creator": "Unknown",
                "source": "wikimedia",
            },
        ]
    }
    with patch("httpx.Client.get", return_value=mock_resp):
        candidates = scraper._search_openverse_photos("Abiy Ahmed", seen_urls=set(), limit=5)
        assert len(candidates) == 1
        assert candidates[0].title == "Prime Minister Abiy Ahmed at African Union Summit"
        assert candidates[0].source == "openverse"
        assert "Paul Kagame" in candidates[0].photographer
        assert candidates[0].image_url == "https://live.staticflickr.com/1234/test.jpg"


def test_search_bing_relevance_filter():
    scraper = WebImageScraper(text_provider=None)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # One relevant photo (Abiy Ahmed), one off-topic photo (Coffee machine)
    mock_resp.text = """
    <html>
      <body>
        <a class="iusc" m='{"murl": "https://example.com/abiy.jpg", "turl": "https://example.com/t1.jpg", "t": "Prime Minister Abiy Ahmed Speech", "purl": "https://news.et/abiy"}'></a>
        <a class="iusc" m='{"murl": "https://example.com/coffee.jpg", "turl": "https://example.com/t2.jpg", "t": "Filter Coffee Machine Best Deals", "purl": "https://shop.com/coffee"}'></a>
      </body>
    </html>
    """
    with patch("httpx.Client.get", return_value=mock_resp):
        candidates = scraper._search_bing_photos("Abiy Ahmed", seen_urls=set(), limit=5)
        # Only the relevant one must be kept; coffee machine must be filtered out!
        assert len(candidates) == 1
        assert candidates[0].title == "Prime Minister Abiy Ahmed Speech"
        assert candidates[0].image_url == "https://example.com/abiy.jpg"

