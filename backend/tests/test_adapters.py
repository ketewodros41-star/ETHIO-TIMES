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
