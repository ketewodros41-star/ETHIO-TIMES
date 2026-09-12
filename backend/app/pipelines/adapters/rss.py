"""Working RSS/Atom source adapter."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from time import mktime

import feedparser
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.pipelines.adapters.base import AdapterError, BaseSourceAdapter, FetchedItem
from app.pipelines.normalize import canonicalize_url, strip_html

logger = get_logger(__name__)


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


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
                headers=self._request_headers(),
            )
            # A conditional request that has not changed is a successful,
            # inexpensive health check. It must never trigger a fallback.
            if response.status_code == 304:
                logger.info("rss_not_modified", source=self.source.slug)
                return []
            response.raise_for_status()
            self._remember_http_validators(response)
            parsed = feedparser.parse(response.content)
            items: list[FetchedItem] = []

            if parsed.entries:
                for entry in parsed.entries:
                    item = self._to_item(entry)
                    if item is not None:
                        items.append(item)
            logger.info(
                "rss_fetch_complete",
                source=self.source.slug,
                items=len(items),
                mode="direct",
            )
            # A valid feed may legitimately be empty. Google News is only a
            # resilience path for a failed direct request, not a replacement
            # feed that can silently change editorial provenance.
            return items
        except Exception as direct_error:
            logger.warning(
                "rss_direct_fetch_failed",
                source=self.source.slug,
                url=self.source.rss_url,
                error=str(direct_error),
            )

        # Fallback only when the configured feed could not be fetched.
        fallback_items = self._fetch_google_news_fallback()
        if fallback_items:
            logger.info(
                "rss_fetch_complete",
                source=self.source.slug,
                items=len(fallback_items),
                mode="google_news_fallback",
            )
            return fallback_items

        raise AdapterError(
            f"Failed to fetch {self.source.rss_url}: {direct_error}"
        ) from direct_error

    def _request_headers(self) -> dict[str, str]:
        headers = dict(BROWSER_HEADERS)
        etag = getattr(self.source, "http_etag", None)
        last_modified = getattr(self.source, "http_last_modified", None)
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def _remember_http_validators(self, response: httpx.Response) -> None:
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")
        if etag:
            self.source.http_etag = etag[:512]
        if last_modified:
            self.source.http_last_modified = last_modified[:512]

    def _fetch_google_news_fallback(self) -> list[FetchedItem]:
        from urllib.parse import urlparse

        domain = None
        if self.source.website:
            domain = urlparse(self.source.website).netloc.replace("www.", "").strip()
        elif self.source.rss_url:
            domain = urlparse(self.source.rss_url).netloc.replace("www.", "").strip()

        if not domain:
            return []

        gn_url = f"https://news.google.com/rss/search?q=site:{domain}&hl=en-US&gl=US&ceid=US:en"
        try:
            resp = httpx.get(
                gn_url,
                headers=BROWSER_HEADERS,
                timeout=settings.ingest_http_timeout_seconds,
                follow_redirects=True,
            )
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            items: list[FetchedItem] = []
            for entry in parsed.entries:
                item = self._to_fallback_item(entry, domain)
                if item is not None:
                    items.append(item)
            return items
        except Exception as exc:
            logger.warning(
                "google_news_fallback_failed",
                source=self.source.slug,
                domain=domain,
                error=str(exc),
            )
            return []

    def _to_fallback_item(self, entry, domain: str) -> FetchedItem | None:  # noqa: ANN001
        link = entry.get("link")
        if not link:
            return None

        raw_title = strip_html(entry.get("title"))
        if " - " in raw_title:
            clean_title = raw_title.rsplit(" - ", 1)[0].strip()
        else:
            clean_title = raw_title

        published_at = self._parse_date(entry)
        summary = strip_html(entry.get("summary"))

        return FetchedItem(
            canonical_url=canonicalize_url(link, base_url=self.source.website or self.source.base_url),
            url=link,
            guid=entry.get("id") or entry.get("guid") or link,
            title=clean_title,
            summary=summary,
            content=summary,
            author=self.source.name,
            language=self.source.language,
            categories=self.source.coverage_categories or ["general"],
            image_url=self._extract_image(entry),
            published_at=published_at,
            raw_payload={"id": entry.get("id"), "link": link, "source": domain},
        )

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
        if media:
            if isinstance(media, list) and len(media) > 0 and isinstance(media[0], dict) and media[0].get("url"):
                return media[0]["url"]
            elif isinstance(media, dict) and media.get("url"):
                return media["url"]
        for link in entry.get("links", []):
            if link.get("rel") == "enclosure":
                href = link.get("href")
                if href and (any(href.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")) or str(link.get("type", "")).startswith("image")):
                    return href
        # Check summary/description/content for <img> tags
        for field in ("summary", "description"):
            val = entry.get(field)
            if val and isinstance(val, str) and "<img" in val.lower():
                m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val, re.IGNORECASE)
                if m:
                    img_src = m.group(1).strip()
                    if img_src.startswith("http") and not any(img_src.lower().endswith(ext) for ext in (".svg", ".gif", ".ico")):
                        return img_src
        if entry.get("content"):
            for c in entry["content"]:
                val = c.get("value") if isinstance(c, dict) else None
                if val and isinstance(val, str) and "<img" in val.lower():
                    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val, re.IGNORECASE)
                    if m:
                        img_src = m.group(1).strip()
                        if img_src.startswith("http") and not any(img_src.lower().endswith(ext) for ext in (".svg", ".gif", ".ico")):
                            return img_src
        return None
