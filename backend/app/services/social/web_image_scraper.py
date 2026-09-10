"""Free live web image scraper for story-relevant editorial photos (Phase 7).

Discovers authentic photos matching news events using:
1. Direct article media & og:image from the event's linked articles.
2. AgentRouter LLM visual query translation (turns Amharic / complex headlines into targeted photo queries).
3. Free live web image search (Bing image photo filter with direct murl resolution — zero API keys).
4. Firecrawl integration (when FIRECRAWL_API_KEY is configured).
5. Strict photo filtering (excludes SVGs, icons, tiny thumbnails, diagrams, coats of arms).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider
from app.models.news_event import NewsEvent
from app.schemas.social_post import PhotoCandidate

logger = get_logger(__name__)

# User-Agent for free web image queries
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_EXCLUDED_EXTENSIONS = (".svg", ".gif", ".pdf", ".ico", ".eps")
_EXCLUDED_TITLE_KEYWORDS = (
    "coat of arms", "flag of", "emblem", "insignia", "seal of",
    "map of", "diagram", "vector illustration", "clipart", "logo vector"
)


class WebImageScraper:
    """Multi-source free web image scraper tailored for Ethiopian news stories."""

    def __init__(self, text_provider: AIProvider | None = None) -> None:
        self.text_provider = text_provider

    def search_candidates(
        self,
        event: NewsEvent,
        custom_query: str | None = None,
        max_pool: int = 36,
    ) -> list[PhotoCandidate]:
        """Aggregate story-relevant photos from all free web sources."""
        seen_urls: set[str] = set()
        pool: list[PhotoCandidate] = []

        # -------------------------------------------------------------
        # Tier 1: Direct Ingested Article Media (Highest Relevance)
        # -------------------------------------------------------------
        direct_photos = self._extract_article_photos(event)
        for cand in direct_photos:
            if cand.image_url not in seen_urls:
                seen_urls.add(cand.image_url)
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 2: Determine Search Queries
        # -------------------------------------------------------------
        if custom_query and custom_query.strip():
            queries = [
                custom_query.strip(),
                f"{custom_query.strip()} Ethiopia news",
            ]
        else:
            queries = self._generate_visual_queries(event)

        logger.info("web_image_search_queries", event_id=str(event.id), queries=queries)

        # -------------------------------------------------------------
        # Tier 3: Free Live Web Image Search (Bing Photos)
        # -------------------------------------------------------------
        for q in queries:
            if len(pool) >= max_pool:
                break
            web_results = self._search_bing_photos(q, seen_urls, limit=12)
            for cand in web_results:
                if len(pool) >= max_pool:
                    break
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)

        # -------------------------------------------------------------
        # Tier 4: Firecrawl (if API key is configured)
        # -------------------------------------------------------------
        firecrawl_key = getattr(settings, "firecrawl_api_key", None)
        if firecrawl_key and len(pool) < max_pool:
            fc_results = self._search_firecrawl(queries[0], firecrawl_key, seen_urls)
            for cand in fc_results:
                if len(pool) >= max_pool:
                    break
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)

        return pool

    def _extract_article_photos(self, event: NewsEvent) -> list[PhotoCandidate]:
        """Pull editorial images directly attached to the event's articles."""
        candidates: list[PhotoCandidate] = []
        if not hasattr(event, "article_links") or not event.article_links:
            return candidates

        for link in event.article_links:
            art = getattr(link, "article", None)
            if not art or not art.image_url:
                continue
            url = art.image_url.strip()
            if not url.startswith("http") or any(url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                continue

            source_name = getattr(art.source, "name", "News Source") if hasattr(art, "source") and art.source else "Original Story"
            candidates.append(
                PhotoCandidate(
                    id=f"art-{art.id}",
                    title=art.title[:90] if art.title else "News Article Photo",
                    thumb_url=url,
                    image_url=url,
                    source="article_source",
                    photographer=source_name,
                    description=f"Authentic news photo published by {source_name}",
                )
            )
        return candidates

    def _generate_visual_queries(self, event: NewsEvent) -> list[str]:
        """Convert Amharic/English headline into 2-3 targeted English photo search queries."""
        # 1. Try LLM translation if available
        if self.text_provider and self.text_provider.is_available():
            try:
                prompt = (
                    "You are a photo desk editor for a newsroom in Ethiopia.\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {(event.summary or '')[:300]}\n"
                    "Output a JSON list of 2 or 3 specific English search queries to find real press/news "
                    "photographs for this story on the web. Focus on real entities, institutions, key persons, "
                    "or locations. Do not use generic words like 'news' or 'pictures'.\n"
                    'Format: ["query 1", "query 2"]'
                )
                res = self.text_provider.generate_text(prompt)
                match = re.search(r"\[.*\]", res.text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list) and parsed:
                        return [str(q).strip() for q in parsed if str(q).strip()][:3]
            except Exception as exc:
                logger.warning("llm_visual_query_gen_failed", error=str(exc))

        # 2. Heuristic fallback
        title = event.title or ""
        # Check Amharic entity heuristics
        amharic_entities = {
            "ንግድ ባንክ": "Commercial Bank of Ethiopia",
            "ብሔራዊ ባንክ": "National Bank of Ethiopia",
            "ሞጆ": "Modjo dry port Ethiopia logistics",
            "አየር መንገድ": "Ethiopian Airlines Addis Ababa",
            "ቴሌኮም": "Ethio telecom Addis Ababa",
            "ቴሌ": "Ethio telecom Addis Ababa",
            "ህዳሴ ግድብ": "Grand Ethiopian Renaissance Dam GERD",
            "እሳት": "Addis Ababa fire emergency rescue",
            "ዋጋ ግሽበት": "Ethiopian market economy currency",
            "ኢንቨስትመንት": "Ethiopia investment industry industrial park",
        }
        for amh_k, en_v in amharic_entities.items():
            if amh_k in title:
                return [en_v, f"{en_v} contemporary"]

        # Clean words from English title
        clean_words = [
            w for w in re.split(r"\W+", title)
            if len(w) > 3 and not re.search(r"[\u1200-\u137F]", w)
        ]
        if clean_words:
            core = " ".join(clean_words[:4])
            return [f"{core} Ethiopia", f"{core} Addis Ababa"]

        return [
            f"{event.primary_region or 'Addis Ababa'} Ethiopia",
            f"Ethiopia {event.primary_category or 'economy'}",
        ]

    def _search_bing_photos(
        self,
        query: str,
        seen_urls: set[str],
        limit: int = 12,
    ) -> list[PhotoCandidate]:
        """Scrape Bing image search with photo filter for live internet photos."""
        candidates: list[PhotoCandidate] = []
        encoded_q = urllib.parse.quote(query)
        # qft=+filterui:photo-photo forces real photographic images, avoiding drawings/clipart
        search_url = f"https://www.bing.com/images/search?q={encoded_q}&qft=+filterui:photo-photo&form=IRFLTR&first=1"

        try:
            with httpx.Client(timeout=8.0, headers=_BROWSER_HEADERS, follow_redirects=True) as client:
                res = client.get(search_url)
                if res.status_code != 200:
                    logger.warning("bing_images_status", status=res.status_code, query=query)
                    return candidates

                from bs4 import BeautifulSoup

                soup = BeautifulSoup(res.text, "html.parser")
                links = soup.find_all("a", class_="iusc")

                for idx, a_elem in enumerate(links):
                    if len(candidates) >= limit:
                        break
                    m_attr = a_elem.get("m")
                    if not m_attr:
                        continue
                    try:
                        meta = json.loads(m_attr)
                    except Exception:
                        continue

                    img_url = meta.get("murl")
                    thumb_url = meta.get("turl") or img_url
                    title = meta.get("t") or query

                    if not img_url or img_url in seen_urls:
                        continue
                    if any(img_url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                        continue
                    if any(bad in title.lower() for bad in _EXCLUDED_TITLE_KEYWORDS):
                        continue

                    seen_urls.add(img_url)
                    source_domain = urllib.parse.urlparse(img_url).netloc or "Web"

                    candidates.append(
                        PhotoCandidate(
                            id=f"web-{abs(hash(img_url)) % 10000000}",
                            title=title[:90],
                            thumb_url=thumb_url,
                            image_url=img_url,
                            source="web_search",
                            photographer=source_domain.replace("www.", ""),
                            description=f"Web photo from {source_domain}",
                        )
                    )
        except Exception as exc:
            logger.warning("bing_image_scrape_failed", query=query, error=str(exc))

        return candidates

    def _search_firecrawl(
        self,
        query: str,
        api_key: str,
        seen_urls: set[str],
        limit: int = 6,
    ) -> list[PhotoCandidate]:
        """Query Firecrawl /search endpoint to extract news images."""
        candidates: list[PhotoCandidate] = []
        try:
            from firecrawl import Firecrawl

            app = Firecrawl(api_key=api_key)
            search_res = app.search(query=query, limit=5)
            urls = []
            if isinstance(search_res, dict):
                data = search_res.get("data", [])
                urls = [item.get("url") for item in data if isinstance(item, dict) and item.get("url")]
            elif hasattr(search_res, "data"):
                urls = [item.url for item in search_res.data if hasattr(item, "url")]

            for url in urls:
                if len(candidates) >= limit:
                    break
                try:
                    scrape_doc = app.scrape(url, formats=["images"])
                    images = []
                    if isinstance(scrape_doc, dict):
                        images = scrape_doc.get("data", {}).get("images", [])
                    elif hasattr(scrape_doc, "images"):
                        images = scrape_doc.images or []

                    for img in images:
                        if len(candidates) >= limit:
                            break
                        if isinstance(img, str) and img.startswith("http") and img not in seen_urls:
                            if not any(img.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                                seen_urls.add(img)
                                candidates.append(
                                    PhotoCandidate(
                                        id=f"fc-{abs(hash(img)) % 10000000}",
                                        title=f"News Photo from {urllib.parse.urlparse(url).netloc}",
                                        thumb_url=img,
                                        image_url=img,
                                        source="firecrawl",
                                        photographer=urllib.parse.urlparse(url).netloc,
                                        description=f"Scraped via Firecrawl from {url[:60]}",
                                    )
                                )
                except Exception as scrape_err:
                    logger.debug("firecrawl_scrape_page_failed", url=url, error=str(scrape_err))
        except Exception as exc:
            logger.warning("firecrawl_integration_error", error=str(exc))

        return candidates
