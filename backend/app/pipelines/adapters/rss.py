"""Working RSS/Atom source adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from time import mktime

import feedparser
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.pipelines.adapters.base import AdapterError, BaseSourceAdapter, FetchedItem
from app.pipelines.normalize import canonicalize_url, strip_html

logger = get_logger(__name__)


class RSSSourceAdapter(BaseSourceAdapter):
    source_type_label = "rss"

    def can_handle(self) -> bool:
        return bool(self.source.rss_url)

    def fetch(self) -> list[FetchedItem]:
        if not self.source.rss_url:
            raise AdapterError(f"Source {self.source.slug} has no rss_url")

        try:
            response = httpx.get(
                self.source.rss_url,
                timeout=settings.ingest_http_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": settings.ingest_user_agent},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterError(f"HTTP error fetching {self.source.rss_url}: {exc}") from exc

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise AdapterError(
                f"Failed to parse feed {self.source.rss_url}: {parsed.bozo_exception}"
            )

        items: list[FetchedItem] = []
        for entry in parsed.entries:
            item = self._to_item(entry)
            if item is not None:
                items.append(item)

        logger.info(
            "rss_fetch_complete",
            source=self.source.slug,
            entries=len(parsed.entries),
            items=len(items),
        )
        return items

    def _to_item(self, entry) -> FetchedItem | None:  # noqa: ANN001 - feedparser dict
        link = entry.get("link")
        if not link:
            return None

        canonical = canonicalize_url(link, base_url=self.source.base_url)
        published_at = self._parse_date(entry)
        categories = [t.get("term") for t in entry.get("tags", []) if t.get("term")]

        summary = strip_html(entry.get("summary"))
        content = None
        if entry.get("content"):
            content = strip_html(entry["content"][0].get("value"))

        return FetchedItem(
            canonical_url=canonical,
            url=link,
            guid=entry.get("id") or entry.get("guid") or link,
            title=strip_html(entry.get("title")),
            summary=summary,
            content=content,
            author=entry.get("author"),
            language=self.source.language,
            categories=categories,
            image_url=self._extract_image(entry),
            published_at=published_at,
            raw_payload={
                "id": entry.get("id"),
                "link": link,
                "tags": categories,
            },
        )

    @staticmethod
    def _parse_date(entry) -> datetime | None:  # noqa: ANN001
        for key in ("published_parsed", "updated_parsed"):
            value = entry.get(key)
            if value:
                return datetime.fromtimestamp(mktime(value), tz=UTC)
        return None

    @staticmethod
    def _extract_image(entry) -> str | None:  # noqa: ANN001
        media = entry.get("media_content") or entry.get("media_thumbnail")
        if media and isinstance(media, list) and media[0].get("url"):
            return media[0]["url"]
        for link in entry.get("links", []):
            if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith(
                "image"
            ):
                return link.get("href")
        return None
