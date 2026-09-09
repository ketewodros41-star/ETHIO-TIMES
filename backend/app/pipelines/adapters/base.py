"""Base source adapter interface and the normalized item it yields."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.news_source import NewsSource


@dataclass
class FetchedItem:
    """A single content item fetched from a source, pre-persistence.

    Adapters normalize whatever the source returns into this shape. The
    ingestion service is responsible for deduplication, relevance scoring, and
    persistence — adapters only fetch and normalize.
    """

    canonical_url: str
    url: str | None = None
    guid: str | None = None
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    author: str | None = None
    language: str | None = None
    categories: list[str] = field(default_factory=list)
    image_url: str | None = None
    published_at: datetime | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class AdapterError(RuntimeError):
    """Raised when an adapter fails to fetch or parse a source."""


class BaseSourceAdapter(ABC):
    """Contract every source adapter implements.

    Concrete adapters: RSS (implemented), Website crawler / API / Telegram
    (stubs for later phases).
    """

    source_type_label: str = "base"

    def __init__(self, source: NewsSource) -> None:
        self.source = source

    @abstractmethod
    def can_handle(self) -> bool:
        """Whether this adapter has enough configuration to run for the source."""
        ...

    @abstractmethod
    def fetch(self) -> list[FetchedItem]:
        """Fetch and normalize the latest items from the source."""
        ...
