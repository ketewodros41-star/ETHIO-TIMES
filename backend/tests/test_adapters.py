"""Tests for adapter selection and the RSS adapter parsing (offline)."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import SourceType
from app.pipelines.adapters.factory import get_adapter_for_source
from app.pipelines.adapters.rss import RSSSourceAdapter
from app.pipelines.adapters.telegram import TelegramSourceAdapter
from app.pipelines.adapters.website import WebsiteCrawlerAdapter


def _source(**kwargs):
    defaults = {
        "rss_url": None,
        "api_url": None,
        "base_url": None,
        "telegram_username": None,
        "telegram_url": None,
        "source_type": SourceType.independent_media,
        "language": "en",
        "slug": "test",
        "http_etag": None,
        "http_last_modified": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_factory_prefers_rss():
    src = _source(rss_url="https://example.com/feed/")
    assert isinstance(get_adapter_for_source(src), RSSSourceAdapter)


def test_factory_routes_telegram_when_no_rss():
    src = _source(source_type=SourceType.telegram_channel)
    assert isinstance(get_adapter_for_source(src), TelegramSourceAdapter)


def test_factory_falls_back_to_website():
    src = _source(base_url="https://example.com")
    assert isinstance(get_adapter_for_source(src), WebsiteCrawlerAdapter)


def test_rss_adapter_can_handle_requires_rss_url():
    assert RSSSourceAdapter(_source(rss_url="x")).can_handle() is True
    assert RSSSourceAdapter(_source()).can_handle() is False


def test_rss_adapter_sends_cached_validators():
    adapter = RSSSourceAdapter(
        _source(
            rss_url="https://example.com/feed/",
            http_etag='"version-7"',
            http_last_modified="Tue, 10 Sep 2026 10:00:00 GMT",
        )
    )

    headers = adapter._request_headers()

    assert headers["If-None-Match"] == '"version-7"'
    assert headers["If-Modified-Since"] == "Tue, 10 Sep 2026 10:00:00 GMT"


def test_rss_not_modified_is_a_successful_empty_fetch(monkeypatch):
    class NotModified:
        status_code = 304
        headers = {}
        content = b""

        def raise_for_status(self):  # pragma: no cover - must not be called
            raise AssertionError("304 must not be treated as a failure")

    monkeypatch.setattr("app.pipelines.adapters.rss.httpx.get", lambda *args, **kwargs: NotModified())

    assert RSSSourceAdapter(_source(rss_url="https://example.com/feed/")).fetch() == []
