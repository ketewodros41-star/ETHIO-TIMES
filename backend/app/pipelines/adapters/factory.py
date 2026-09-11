"""Select the appropriate adapter for a source.

Phase 1 routes to the RSS adapter whenever an `rss_url` is present; otherwise it
returns the best stub adapter for the source's configuration so the ingestion
service can record a clear "not implemented yet" outcome.
"""

from __future__ import annotations

from app.models.enums import SourceType
from app.models.news_source import NewsSource
from app.pipelines.adapters.api import APISourceAdapter
from app.pipelines.adapters.base import BaseSourceAdapter
from app.pipelines.adapters.rss import RSSSourceAdapter
from app.pipelines.adapters.telegram import TelegramSourceAdapter
from app.pipelines.adapters.website import WebsiteCrawlerAdapter


def get_adapter_for_source(source: NewsSource) -> BaseSourceAdapter:
    if source.rss_url:
        return RSSSourceAdapter(source)
    if source.source_type == SourceType.telegram_channel:
        return TelegramSourceAdapter(source)
    if source.api_url:
        return APISourceAdapter(source)
    return WebsiteCrawlerAdapter(source)
