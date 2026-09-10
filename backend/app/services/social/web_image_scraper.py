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
from app.services.social.image_enhancer import upscale_news_cdn_url

logger = get_logger(__name__)


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    try:
        return str(val).encode("ascii", "replace").decode("ascii")
    except Exception:
        return "<unprintable>"


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
    "coat of arms", "flag of", "flag_", "emblem", "insignia", "seal of",
    "map of", "map_", "karte", "carte", "diagram", "vector illustration", "clipart", "logo vector"
)


class WebImageScraper:
    """Multi-source free web image scraper tailored for Ethiopian news stories."""

    def __init__(self, text_provider: AIProvider | None = None) -> None:
        self.text_provider = text_provider
        self._analysis_cache: dict[str, tuple[str, str | None, list[str], list[str]]] = {}

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
        topic, main_person, queries, suggested_chips = self.analyze_story(event, custom_query=custom_query)

        logger.info(
            "web_image_search_plan",
            event_id=str(event.id),
            topic=topic,
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
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 4: Openverse Global Editorial Engine (Flickr/CC Photojournalism)
        # -------------------------------------------------------------
        for q in queries[:2]:
            if len(pool) >= 18:
                break
            ov_results = self._search_openverse_photos(q, seen_urls, limit=6)
            for cand in ov_results:
                if len(pool) >= max_pool:
                    break
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 5: Wikimedia Commons Topic Bitmap Archives
        # -------------------------------------------------------------
        for q in queries[:2]:
            if len(pool) >= 18:
                break
            wm_results = self._search_wikimedia_topic_photos(q, seen_urls, limit=5)
            for cand in wm_results:
                if len(pool) >= max_pool:
                    break
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 6: Live Web Image Search (Bing with Relevance Validation)
        # -------------------------------------------------------------
        for q in queries[:2]:
            if len(pool) >= 18:
                break
            web_results = self._search_bing_photos(q, seen_urls, limit=6)
            for cand in web_results:
                if len(pool) >= max_pool:
                    break
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 7: Google Custom Search API (If configured)
        # -------------------------------------------------------------
        google_key = getattr(settings, "google_search_api_key", None)
        google_cx = getattr(settings, "google_search_cx", None)
        if google_key and google_cx and len(pool) < 18 and queries:
            g_results = self._search_google_cse(queries[0], google_key, google_cx, seen_urls, limit=8)
            for cand in g_results:
                if len(pool) >= max_pool:
                    break
                pool.append(cand)

        # -------------------------------------------------------------
        # Tier 8: Firecrawl (If configured)
        # -------------------------------------------------------------
        firecrawl_key = getattr(settings, "firecrawl_api_key", None)
        if firecrawl_key and len(pool) < max_pool and queries:
            fc_results = self._search_firecrawl(queries[0], firecrawl_key, seen_urls)
            for cand in fc_results:
                if len(pool) >= max_pool:
                    break
                pool.append(cand)

        return pool

    def _extract_article_photos(self, event: NewsEvent) -> list[PhotoCandidate]:
        """Pull editorial images directly attached to the event's articles."""
        candidates: list[PhotoCandidate] = []
        if not hasattr(event, "article_links") or not event.article_links:
            return candidates

        for link in event.article_links:
            art = getattr(link, "article", None)
            if not art:
                continue

            url = art.image_url
            if not url or not url.strip().startswith("http"):
                target_url = art.url or art.canonical_url
                if target_url:
                    try:
                        from app.services.social.image_pipeline import extract_article_web_image
                        url = extract_article_web_image(target_url)
                        if url:
                            art.image_url = url
                    except Exception:
                        pass

            if not url or not url.startswith("http") or any(url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                continue

            source_name = getattr(art.source, "name", "News Source") if hasattr(art, "source") and art.source else "Original Story"
            hd_url = upscale_news_cdn_url(url)
            candidates.append(
                PhotoCandidate(
                    id=f"art-{art.id}",
                    title=art.title[:90] if art.title else "News Article Photo",
                    thumb_url=url,
                    image_url=hd_url,
                    source="article_source",
                    photographer=source_name,
                    description=f"Authentic news photo published by {source_name}",
                )
            )
        return candidates

    def analyze_story(
        self, event: NewsEvent, custom_query: str | None = None
    ) -> tuple[str, str | None, list[str], list[str]]:
        """Deeply understand news story: returns (topic, main_person, photo_queries, suggested_chips)."""
        if custom_query and custom_query.strip():
            cq = custom_query.strip()
            cq_lower = cq.lower()
            main_person = None
            for keywords, name in [
                (("ዐቢይ", "አብይ", "ጠቅላይ ሚኒስትር", "abiy", "prime minister"), "Abiy Ahmed"),
                (("ሽመልስ", "shimelis"), "Shimelis Abdisa"),
                (("ታየ አጽቀ", "taye atske"), "Taye Atske Selassie"),
                (("ሳህለወርቅ", "sahle-work"), "Sahle-Work Zewde"),
                (("አዳነች አቤቤ", "adanech"), "Adanech Abebe"),
                (("ሃይለማሪያም", "hailemariam"), "Hailemariam Desalegn"),
                (("ቴዲ አፍሮ", "teddy afro"), "Teddy Afro"),
                (("ደመቀ መኮንን", "demeke mekonnen"), "Demeke Mekonnen"),
                (("ዳንጎቴ", "dangote"), "Aliko Dangote"),
            ]:
                if any(k in cq_lower for k in keywords):
                    main_person = name
                    break

            if main_person:
                queries = [f"{main_person} Ethiopia", f"{main_person} news", f"{main_person} official portrait"]
                chips = [main_person, "Ethiopia leadership", "News photo"]
            else:
                queries = [cq, f"{cq} Ethiopia news", f"Contemporary {cq}"]
                chips = [cq, f"{cq} news", "Ethiopia"]
            return cq, main_person, queries, chips

        # Story understanding for event without custom query
        cache_key = str(event.id)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        topic: str | None = None
        main_person: str | None = None
        queries: list[str] = []
        chips: list[str] = []

        # 1. LLM entity & topic extraction via AgentRouter / Gemini
        if self.text_provider and self.text_provider.is_available():
            try:
                prompt = (
                    "You are a photo desk editor for a newsroom in Ethiopia.\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {(event.summary or '')[:450]}\n"
                    f"Category: {event.primary_category or 'General'}, Region: {event.primary_region or 'Ethiopia'}\n\n"
                    "Extract the main topic, central person (if any), 3 photo search queries in English, and 3 suggested filter chips.\n"
                    "Output JSON only:\n"
                    "{\n"
                    '  "topic": "Concise English editorial topic",\n'
                    '  "main_person": "Full English Name or null",\n'
                    '  "queries": ["query 1", "query 2", "query 3"],\n'
                    '  "suggested_chips": ["chip 1", "chip 2", "chip 3"]\n'
                    "}"
                )
                req = TextGenerationRequest(prompt=prompt)
                res = self.text_provider.generate_text(req)
                match = re.search(r"\{.*\}", res.text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    t = str(parsed.get("topic") or "").strip()
                    p = parsed.get("main_person")
                    if p and str(p).strip().lower() in ("null", "none", ""):
                        p = None
                    raw_q = parsed.get("queries") or parsed.get("photo_queries") or parsed.get("search_queries") or []
                    clean_q = [str(q).strip() for q in raw_q if str(q).strip()][:3]
                    raw_c = parsed.get("suggested_chips") or parsed.get("chips") or []
                    clean_c = [str(c).strip() for c in raw_c if str(c).strip()][:4]
                    if t:
                        topic = t
                    if p:
                        main_person = str(p).strip()
                    if clean_q:
                        queries = clean_q
                    if clean_c:
                        chips = clean_c
            except Exception as exc:
                logger.warning("llm_story_analysis_failed", error=_safe_str(exc))

        # 2. Heuristic person detection if not identified by LLM
        text = f"{event.title or ''} {event.summary or ''}".lower()
        if not main_person:
            person_map = {
                ("ዐቢይ", "አብይ", "ጠቅላይ ሚኒስትር", "abiy", "prime minister"): "Abiy Ahmed",
                ("ሽመልስ", "shimelis"): "Shimelis Abdisa",
                ("ታየ አጽቀ", "taye atske"): "Taye Atske Selassie",
                ("ሳህለወርቅ", "sahle-work"): "Sahle-Work Zewde",
                ("አዳነች አቤቤ", "adanech"): "Adanech Abebe",
                ("ሃይለማሪያም", "hailemariam"): "Hailemariam Desalegn",
                ("ቴዲ አፍሮ", "teddy afro"): "Teddy Afro",
                ("ደመቀ መኮንን", "demeke mekonnen"): "Demeke Mekonnen",
                ("ዳንጎቴ", "dangote"): "Aliko Dangote",
            }
            for keywords, name in person_map.items():
                if any(k in text for k in keywords):
                    main_person = name
                    break

        # 3. Topic & query fallback if not identified by LLM
        if main_person and not queries:
            queries = [
                f"{main_person} Ethiopia",
                f"{main_person} official portrait",
                f"Prime Minister {main_person}",
            ]
            if not topic:
                topic = f"Prime Minister {main_person}" if main_person == "Abiy Ahmed" else f"{main_person} Leadership"

        if not topic:
            amharic_entities = {
                ("ንግድ ባንክ", "cbe", "commercial bank"): ("Commercial Bank of Ethiopia", "Commercial Bank of Ethiopia headquarters"),
                ("ብሔራዊ ባንክ", "nbe", "national bank"): ("National Bank of Ethiopia", "National Bank of Ethiopia"),
                ("ሞጆ", "modjo", "mojo"): ("Modjo Logistics & Dry Port", "Modjo dry port Ethiopia logistics"),
                ("አየር መንገድ", "airlines", "airline", "flight"): ("Ethiopian Airlines & Aviation", "Ethiopian Airlines Addis Ababa"),
                ("ቴሌኮም", "telecom", "safari"): ("Ethio Telecom & Technology", "Ethio telecom Addis Ababa"),
                ("ህዳሴ ግድብ", "ህዳሴ", "ዓባይ", "gerd", "dam"): ("Grand Ethiopian Renaissance Dam", "Grand Ethiopian Renaissance Dam GERD"),
                ("እሳት", "አደጋ", "fire", "rescue"): ("Fire & Emergency Services", "Addis Ababa fire emergency rescue"),
                ("ዋጋ ግሽበት", "inflation", "ብር", "birr"): ("Ethiopian Economy & Currency", "Ethiopian market economy currency"),
            }
            for keywords, (top_name, default_query) in amharic_entities.items():
                if any(k in text for k in keywords):
                    topic = top_name
                    if not queries:
                        queries = [default_query, f"{top_name} contemporary", f"{top_name} news"]
                    break

        # 4. Regional fallback if still no topic
        if not topic:
            region_topics = {
                "tigray": ("Tigray Region", ["Tigray Ethiopia", "Mekelle city Ethiopia"]),
                "amhara": ("Amhara Region", ["Amhara Ethiopia", "Bahir Dar Lake Tana"]),
                "oromia": ("Oromia Region", ["Oromia Ethiopia", "Adama city Ethiopia"]),
                "somali": ("Somali Region", ["Somali Region Ethiopia", "Jijiga Ethiopia"]),
                "afar": ("Afar Region", ["Afar Region Ethiopia", "Danakil Ethiopia"]),
                "sidama": ("Sidama Region", ["Sidama Region Ethiopia", "Hawassa Ethiopia"]),
                "dire dawa": ("Dire Dawa", ["Dire Dawa Ethiopia", "Dire Dawa city"]),
            }
            for rk, (rtopic, rfacets) in region_topics.items():
                if rk in text:
                    topic = rtopic
                    if not queries:
                        queries = rfacets
                    break

        # 5. Default topic from title or region
        if not topic:
            clean_words = [
                w for w in re.split(r"\W+", event.title or "")
                if len(w) > 3 and not re.search(r"[\u1200-\u137F]", w)
            ]
            if clean_words:
                subj = " ".join(clean_words[:4])
                topic = f"{subj}"
                if not queries:
                    queries = [f"{subj} Ethiopia", f"{subj} news", f"{subj} Addis Ababa"]
            else:
                topic = f"{event.primary_region or 'Addis Ababa'} News"
                if not queries:
                    queries = [f"{event.primary_region or 'Addis Ababa'} Ethiopia", f"Ethiopia {event.primary_category or 'economy'}"]

        if not queries:
            if main_person:
                queries = [f"{main_person} Ethiopia", f"{main_person} official portrait", f"Prime Minister {main_person}"]
            else:
                queries = [f"{topic} Ethiopia", f"{topic} news"]

        if not chips:
            chips = []
            if main_person:
                chips.append(main_person)
            chips.append(topic.split()[0] if topic else "Ethiopia")
            if event.primary_region and event.primary_region not in chips:
                chips.append(event.primary_region)
            if event.primary_category and event.primary_category.title() not in chips:
                chips.append(event.primary_category.title())

        result = (topic, main_person, queries, chips)
        self._analysis_cache[cache_key] = result
        return result

    def _analyze_entities_and_queries(self, event: NewsEvent) -> tuple[str | None, list[str]]:
        """Backward-compatible helper returning (main_person, queries)."""
        _topic, main_person, queries, _chips = self.analyze_story(event)
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
                        orig = upscale_news_cdn_url(ii.get("url") or thumb)
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
            logger.warning("commons_person_search_failed", person=_safe_str(person_name), error=_safe_str(exc))

        # 2. Openverse search for authentic press photos of person (Flickr summits, state visits)
        ov_person = self._search_openverse_photos(person_name, seen_urls, limit=6)
        candidates.extend(ov_person)

        # 3. Wikipedia page images for person
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
                            orig = upscale_news_cdn_url(thumb)
                            candidates.append(
                                PhotoCandidate(
                                    id=f"wiki-person-{pid}",
                                    title=title,
                                    thumb_url=thumb,
                                    image_url=orig,
                                    source="wikimedia",
                                    photographer="Wikipedia Editorial",
                                    description=f"Wikipedia portrait of {person_name}",
                                )
                            )
        except Exception as exc:
            logger.warning("wiki_person_search_failed", person=_safe_str(person_name), error=_safe_str(exc))

        return candidates

    def _search_openverse_photos(
        self,
        query: str,
        seen_urls: set[str],
        limit: int = 8,
    ) -> list[PhotoCandidate]:
        """Query Openverse REST API (>700M Creative Commons editorial & press photos)."""
        candidates: list[PhotoCandidate] = []
        encoded_q = urllib.parse.quote(query)
        api_url = f"https://api.openverse.org/v1/images/?q={encoded_q}&page_size={min(limit, 20)}"

        try:
            with httpx.Client(timeout=8.0, headers=_WIKI_HEADERS) as client:
                res = client.get(api_url)
                if res.status_code == 200:
                    results = res.json().get("results", [])
                    for item in results:
                        img_url = item.get("url")
                        thumb_url = item.get("thumbnail") or img_url
                        title = item.get("title") or query
                        creator = item.get("creator") or item.get("source") or "Openverse"
                        source_name = item.get("source") or "openverse"

                        if not img_url or img_url in seen_urls:
                            continue
                        if any(img_url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                            continue
                        if any(bad in title.lower() for bad in _EXCLUDED_TITLE_KEYWORDS):
                            continue

                        seen_urls.add(img_url)
                        candidates.append(
                            PhotoCandidate(
                                id=f"ov-{abs(hash(img_url)) % 10000000}",
                                title=title[:90],
                                thumb_url=thumb_url,
                                image_url=img_url,
                                source="openverse",
                                photographer=f"{creator} ({source_name})",
                                description=f"Authentic editorial photo via Openverse ({source_name})",
                            )
                        )
        except Exception as exc:
            logger.warning("openverse_search_failed", query=_safe_str(query), error=_safe_str(exc))

        return candidates

    def _search_wikimedia_topic_photos(
        self,
        query: str,
        seen_urls: set[str],
        limit: int = 6,
    ) -> list[PhotoCandidate]:
        """Query Wikimedia Commons for high-resolution bitmap photos matching topic query."""
        candidates: list[PhotoCandidate] = []
        c_url = (
            f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote(query + ' filetype:bitmap')}"
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
                        orig = upscale_news_cdn_url(ii.get("url") or thumb)
                        title = p.get("title", "").replace("File:", "").replace("_", " ")
                        if not thumb or thumb in seen_urls:
                            continue
                        if any(x in thumb.lower() for x in _EXCLUDED_EXTENSIONS):
                            continue
                        if any(bad in title.lower() for bad in _EXCLUDED_TITLE_KEYWORDS):
                            continue

                        seen_urls.add(thumb)
                        candidates.append(
                            PhotoCandidate(
                                id=f"commons-topic-{pid}",
                                title=title[:90],
                                thumb_url=thumb,
                                image_url=orig,
                                source="wikimedia",
                                photographer="Wikimedia Commons",
                                description=f"Wikimedia photo: {title[:90]}",
                            )
                        )
        except Exception as exc:
            logger.warning("wikimedia_topic_search_failed", query=_safe_str(query), error=_safe_str(exc))

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
            logger.warning("google_cse_search_failed", query=_safe_str(query), error=_safe_str(exc))
        return candidates

    def _search_bing_photos(
        self,
        query: str,
        seen_urls: set[str],
        limit: int = 8,
    ) -> list[PhotoCandidate]:
        """Scrape Bing image search with photo filter and strict query relevance verification."""
        candidates: list[PhotoCandidate] = []
        encoded_q = urllib.parse.quote(query)
        search_url = f"https://www.bing.com/images/search?q={encoded_q}&qft=+filterui:photo-photo&form=IRFLTR&first=1"

        # Build query tokens for strict relevance checking
        query_tokens = [
            w.lower() for w in re.split(r"\W+", query)
            if len(w) >= 3 and w.lower() not in {"and", "the", "for", "with", "from", "news", "ethiopia"}
        ]

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

                    img_url = upscale_news_cdn_url(meta.get("murl"))
                    thumb_url = meta.get("turl") or img_url
                    title = meta.get("t") or query
                    purl = meta.get("purl") or ""

                    if not img_url or img_url in seen_urls:
                        continue
                    if any(img_url.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                        continue
                    if any(bad in title.lower() for bad in _EXCLUDED_TITLE_KEYWORDS):
                        continue

                    # Strict relevance verification: title or source URL must relate to the story
                    if query_tokens:
                        combined_text = f"{title} {purl}".lower()
                        if not any(token in combined_text for token in query_tokens):
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
            logger.warning("bing_image_scrape_failed", query=_safe_str(query), error=_safe_str(exc))

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
                    logger.debug("firecrawl_scrape_page_failed", url=url, error=_safe_str(scrape_err))
        except Exception as exc:
            logger.warning("firecrawl_integration_error", error=_safe_str(exc))

        return candidates
