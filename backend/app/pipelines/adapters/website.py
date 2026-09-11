"""Website crawler adapter — fetches news for web sources without direct RSS feeds."""

from __future__ import annotations

from datetime import UTC, datetime
from time import mktime
from urllib.parse import urlparse

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


class WebsiteCrawlerAdapter(BaseSourceAdapter):
    source_type_label = "website"

    def can_handle(self) -> bool:
        return bool(self.source.website or self.source.base_url)

    def fetch(self) -> list[FetchedItem]:
        url = self.source.website or self.source.base_url
        if not url:
            raise AdapterError(f"Source {self.source.slug} has no website URL")

        domain = urlparse(url).netloc.replace("www.", "").strip()
        if not domain:
            raise AdapterError(f"Cannot parse domain from website: {url}")

        # Fallback to publisher name search if domain is generic government portal
        query = f"site:{domain}" if len(domain) > 3 else f'"{self.source.name}"'
        gn_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        try:
            resp = httpx.get(
                gn_url,
                headers=BROWSER_HEADERS,
                timeout=settings.ingest_http_timeout_seconds,
                follow_redirects=True,
            )
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as exc:
            raise AdapterError(f"Failed to crawl news for {domain}: {exc}") from exc

        items: list[FetchedItem] = []
        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue

            raw_title = strip_html(entry.get("title"))
            if " - " in raw_title:
                clean_title = raw_title.rsplit(" - ", 1)[0].strip()
            else:
                clean_title = raw_title

            published_at = None
            for key in ("published_parsed", "updated_parsed"):
                val = entry.get(key)
                if val:
                    published_at = datetime.fromtimestamp(mktime(val), tz=UTC)
                    break

            summary = strip_html(entry.get("summary"))
            items.append(
                FetchedItem(
                    canonical_url=canonicalize_url(link, base_url=url),
                    url=link,
                    guid=entry.get("id") or entry.get("guid") or link,
                    title=clean_title,
                    summary=summary,
                    content=summary,
                    author=self.source.name,
                    language=self.source.language,
                    categories=self.source.coverage_categories or ["general"],
                    image_url=None,
                    published_at=published_at,
                    raw_payload={"id": entry.get("id"), "link": link, "source": domain},
                )
            )

        logger.info(
            "website_crawl_complete",
            source=self.source.slug,
            domain=domain,
            items=len(items),
        )
        return items
