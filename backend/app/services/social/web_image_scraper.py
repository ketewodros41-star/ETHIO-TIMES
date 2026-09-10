"""Free live web image scraper for story-relevant editorial photos (Phase 7).

Discovers authentic photos matching news events using:
1. Direct article media & og:image from the event's linked articles.
2. AgentRouter LLM entity extraction: identifies key persons (e.g. Prime Minister Abiy Ahmed, Ministers, Mayors)
   and generates specific photographic queries.
3. Person-specific portrait & press photo search (Wikimedia Commons + Wikipedia).
4. Free live web image search (Bing image photo filter).
5. Google Custom Search Engine (CSE) image API (when GOOGLE_SEARCH_API_KEY is configured).
6. Firecrawl integration (when FIRECRAWL_API_KEY is configured).
7. Strict editorial photo filtering (excludes SVGs, icons, tiny thumbnails, diagrams, coats of arms).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, TextGenerationRequest
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

_WIKI_HEADERS = {
    "User-Agent": "ETHIOTIMESBot/1.0 (editorial-studio@ethiotimes.org; contact: info@ethiotimes.com)"
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
        # Tier 2: Entity & Person Analysis (LLM or Heuristic)
        # -------------------------------------------------------------
        if custom_query and custom_query.strip():
            main_person = None
            queries = [custom_query.strip(), f"{custom_query.strip()} Ethiopia news"]
        else:
            main_person, queries = self._analyze_entities_and_queries(event)

        logger.info(
            "web_image_search_plan",
            event_id=str(event.id),
            main_person=main_person,
            queries=queries,
        )

        # -------------------------------------------------------------
        # Tier 3: Person-Specific Search (If a person was identified!)
        # -------------------------------------------------------------
        if main_person:
            person_photos = self._search_person_photos(main_person, seen_urls, limit=12)
            for cand in person_photos:
                if len(pool) >= max_pool:
                    break
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)

        # -------------------------------------------------------------
        # Tier 4: Google Custom Search API (If configured)
        # -------------------------------------------------------------
        google_key = getattr(settings, "google_search_api_key", None)
        google_cx = getattr(settings, "google_search_cx", None)
        if google_key and google_cx and queries:
            g_results = self._search_google_cse(queries[0], google_key, google_cx, seen_urls, limit=8)
            for cand in g_results:
                if len(pool) >= max_pool:
                    break
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)

        # -------------------------------------------------------------
        # Tier 5: Live Web Image Search (Bing Photos)
        # -------------------------------------------------------------
        for q in queries:
            if len(pool) >= max_pool:
                break
            web_results = self._search_bing_photos(q, seen_urls, limit=8)
            for cand in web_results:
                if len(pool) >= max_pool:
                    break
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)

        # -------------------------------------------------------------
        # Tier 6: Firecrawl (If configured)
        # -------------------------------------------------------------
        firecrawl_key = getattr(settings, "firecrawl_api_key", None)
        if firecrawl_key and len(pool) < max_pool and queries:
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

    def _analyze_entities_and_queries(self, event: NewsEvent) -> tuple[str | None, list[str]]:
        """Identify main person (e.g. Abiy Ahmed) and 2-3 specific English photo search queries."""
        # 1. Try LLM entity extraction via AgentRouter
        if self.text_provider and self.text_provider.is_available():
            try:
                prompt = (
                    "You are a photo desk editor for a newsroom in Ethiopia.\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {(event.summary or '')[:350]}\n"
                    "Extract the main individual person (if the story is about a specific leader, minister, president, "
                    "or public figure) and 3 photographic search queries in English.\n"
                    "Output JSON only:\n"
                    "{\n"
                    '  "main_person": "Full English Name or null",\n'
                    '  "queries": ["query 1", "query 2", "query 3"]\n'
                    "}"
                )
                req = TextGenerationRequest(prompt=prompt)
                res = self.text_provider.generate_text(req)
                match = re.search(r"\{.*\}", res.text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    person = parsed.get("main_person")
                    if person and person.strip().lower() in ("null", "none"):
                        person = None
                    queries = parsed.get("queries") or []
                    if isinstance(queries, list) and queries:
                        clean_q = [str(q).strip() for q in queries if str(q).strip()][:3]
                        if person:
                            return person.strip(), clean_q
                        if clean_q:
                            return None, clean_q
            except Exception as exc:
                logger.warning("llm_entity_query_failed", error=str(exc))

        # 2. Heuristic person detection
        text = f"{event.title or ''} {event.summary or ''}".lower()
        person_map = {
            ("ዐቢይ", "አብይ", "ጠቅላይ ሚኒስትር", "abiy", "prime minister"): "Abiy Ahmed",
            ("ሽመልስ", "shimelis"): "Shimelis Abdisa",
            ("ታየ አጽቀ", "taye atske"): "Taye Atske Selassie",
            ("ሳህለወርቅ", "sahle-work"): "Sahle-Work Zewde",
            ("አዳነች አቤቤ", "adanech"): "Adanech Abebe",
            ("ሃይለማሪያም", "hailemariam"): "Hailemariam Desalegn",
            ("ቴዲ አፍሮ", "teddy afro"): "Teddy Afro",
            ("ደመቀ መኮንን", "demeke mekonnen"): "Demeke Mekonnen",
        }
        main_person = None
        for keywords, name in person_map.items():
            if any(k in text for k in keywords):
                main_person = name
                break

        # 3. Heuristic topic fallback
        amharic_entities = {
            "ንግድ ባንክ": "Commercial Bank of Ethiopia",
            "ብሔራዊ ባንክ": "National Bank of Ethiopia",
            "ሞጆ": "Modjo dry port Ethiopia logistics",
            "አየር መንገድ": "Ethiopian Airlines Addis Ababa",
            "ቴሌኮም": "Ethio telecom Addis Ababa",
            "ህዳሴ ግድብ": "Grand Ethiopian Renaissance Dam GERD",
            "እሳት": "Addis Ababa fire emergency rescue",
            "ዋጋ ግሽበት": "Ethiopian market economy currency",
        }
        queries = []
        if main_person:
            queries = [
                f"{main_person} Ethiopia",
                f"{main_person} official portrait",
                f"Prime Minister {main_person}",
            ]
        else:
            for amh_k, en_v in amharic_entities.items():
                if amh_k in text:
                    queries = [en_v, f"{en_v} contemporary"]
                    break

        if not queries:
            clean_words = [
                w for w in re.split(r"\W+", event.title or "")
                if len(w) > 3 and not re.search(r"[\u1200-\u137F]", w)
            ]
            if clean_words:
                core = " ".join(clean_words[:4])
                queries = [f"{core} Ethiopia", f"{core} Addis Ababa"]
            else:
                queries = [
                    f"{event.primary_region or 'Addis Ababa'} Ethiopia",
                    f"Ethiopia {event.primary_category or 'economy'}",
                ]

        return main_person, queries

    def _search_person_photos(
        self,
        person_name: str,
        seen_urls: set[str],
        limit: int = 12,
    ) -> list[PhotoCandidate]:
        """Search Wikimedia Commons and Wikipedia specifically for authentic photos of a named person."""
        candidates: list[PhotoCandidate] = []

        # 1. Wikimedia Commons direct search for person bitmap photos
        c_url = (
            f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote(person_name + ' filetype:bitmap')}"
            f"&gsrnamespace=6&gsrlimit={limit}&prop=imageinfo&iiprop=url&iiurlwidth=1000&format=json"
        )
        try:
            with httpx.Client(timeout=8.0, headers=_WIKI_HEADERS) as client:
                res = client.get(c_url)
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for pid, p in pages.items():
                        ii = p.get("imageinfo", [{}])[0]
                        thumb = ii.get("thumburl") or ii.get("url")
                        orig = ii.get("url") or thumb
                        title = p.get("title", "").replace("File:", "").replace("_", " ")
                        if not thumb or thumb in seen_urls:
                            continue
                        if any(x in thumb.lower() for x in _EXCLUDED_EXTENSIONS):
                            continue
                        seen_urls.add(thumb)
                        candidates.append(
                            PhotoCandidate(
                                id=f"commons-person-{pid}",
                                title=f"{person_name}: {title[:60]}",
                                thumb_url=thumb,
                                image_url=orig,
                                source="wikimedia",
                                photographer="Wikimedia Commons",
                                description=f"Official photograph of {person_name}",
                            )
                        )
        except Exception as exc:
            logger.warning("commons_person_search_failed", person=person_name, error=str(exc))

        # 2. Wikipedia page images for person
        w_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote(person_name)}"
            f"&gsrlimit=6&prop=pageimages|extracts&pithumbsize=1000&exintro=1&explaintext=1&format=json"
        )
        try:
            with httpx.Client(timeout=8.0, headers=_WIKI_HEADERS) as client:
                res = client.get(w_url)
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for pid, p in pages.items():
                        thumb = p.get("thumbnail", {}).get("source")
                        title = p.get("title", "")
                        if not thumb or thumb in seen_urls:
                            continue
                        if any(x in thumb.lower() for x in _EXCLUDED_EXTENSIONS):
                            continue
                        # Relevance check: title must relate to person
                        if any(w.lower() in title.lower() for w in person_name.split()):
                            seen_urls.add(thumb)
                            candidates.append(
                                PhotoCandidate(
                                    id=f"wiki-person-{pid}",
                                    title=title,
                                    thumb_url=thumb,
                                    image_url=thumb,
                                    source="wikimedia",
                                    photographer="Wikipedia Editorial",
                                    description=f"Wikipedia portrait of {person_name}",
                                )
                            )
        except Exception as exc:
            logger.warning("wiki_person_search_failed", person=person_name, error=str(exc))

        return candidates

    def _search_google_cse(
        self,
        query: str,
        api_key: str,
        cx: str,
        seen_urls: set[str],
        limit: int = 8,
    ) -> list[PhotoCandidate]:
        """Query Google Custom Search JSON API for high-resolution images."""
        candidates: list[PhotoCandidate] = []
        try:
            params = {
                "key": api_key,
                "cx": cx,
                "q": query,
                "searchType": "image",
                "num": min(limit, 10),
                "safe": "active",
            }
            with httpx.Client(timeout=8.0) as client:
                res = client.get("https://www.googleapis.com/customsearch/v1", params=params)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("items", [])
                    for item in items:
                        img_url = item.get("link")
                        thumb_url = item.get("image", {}).get("thumbnailLink") or img_url
                        title = item.get("title") or query
                        source_domain = urllib.parse.urlparse(img_url).netloc
                        if not img_url or img_url in seen_urls:
                            continue
                        if any(img_url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                            continue
                        seen_urls.add(img_url)
                        candidates.append(
                            PhotoCandidate(
                                id=f"google-{abs(hash(img_url)) % 10000000}",
                                title=title[:90],
                                thumb_url=thumb_url,
                                image_url=img_url,
                                source="google_images",
                                photographer=source_domain,
                                description=f"Google Image from {source_domain}",
                            )
                        )
        except Exception as exc:
            logger.warning("google_cse_search_failed", query=query, error=str(exc))
        return candidates

    def _search_bing_photos(
        self,
        query: str,
        seen_urls: set[str],
        limit: int = 8,
    ) -> list[PhotoCandidate]:
        """Scrape Bing image search with photo filter for live internet photos."""
        candidates: list[PhotoCandidate] = []
        encoded_q = urllib.parse.quote(query)
        search_url = f"https://www.bing.com/images/search?q={encoded_q}&qft=+filterui:photo-photo&form=IRFLTR&first=1"

        try:
            with httpx.Client(timeout=8.0, headers=_BROWSER_HEADERS, follow_redirects=True) as client:
                res = client.get(search_url)
                if res.status_code != 200:
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
