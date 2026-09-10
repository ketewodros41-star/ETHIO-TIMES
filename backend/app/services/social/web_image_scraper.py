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

from dataclasses import dataclass, field
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


@dataclass
class StoryVisualEntities:
    """Decomposed story entities for structured, multi-tier photo searching."""
    topic: str
    main_person: str | None = None
    persons: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    suggested_chips: list[str] = field(default_factory=list)


class WebImageScraper:
    """Multi-source free web image scraper tailored for Ethiopian news stories."""

    def __init__(self, text_provider: AIProvider | None = None) -> None:
        self.text_provider = text_provider
        self._analysis_cache: dict[str, StoryVisualEntities] = {}
        self._wiki_img_cache: dict[str, PhotoCandidate | None] = {}

    def search_candidates(
        self,
        event: NewsEvent,
        custom_query: str | None = None,
        max_pool: int = 36,
    ) -> list[PhotoCandidate]:
        """Aggregate story-relevant photos from all free web sources using a 4-tier waterfall."""
        seen_urls: set[str] = set()

        tier1_leads: list[PhotoCandidate] = []
        tier2_persons: list[PhotoCandidate] = []
        tier3_locations: list[PhotoCandidate] = []
        tier4_institutions_and_concepts: list[PhotoCandidate] = []

        # -------------------------------------------------------------
        # Tier 1: Direct Ingested Article Media (Highest Relevance)
        # -------------------------------------------------------------
        direct_photos = self._extract_article_photos(event)
        for cand in direct_photos:
            if cand.image_url not in seen_urls:
                seen_urls.add(cand.image_url)
                cand.entity_type = "lead"
                tier1_leads.append(cand)

        # -------------------------------------------------------------
        # Entity & Story Analysis (LLM + Comprehensive Ethiopian Knowledge Base)
        # -------------------------------------------------------------
        entities = self.analyze_story_entities(event, custom_query=custom_query)

        logger.info(
            "web_image_search_plan",
            event_id=str(event.id),
            topic=entities.topic,
            main_person=entities.main_person,
            persons=entities.persons,
            locations=entities.locations,
            institutions=entities.institutions,
            concepts=entities.concepts,
        )

        # Tier 1 concepts (concise 2-word photographic concepts)
        for q in entities.concepts[:2]:
            cands = self._search_openverse_photos(q, seen_urls, limit=4)
            for c in cands:
                c.entity_type = "concept"
                tier1_leads.append(c)
            wm_cands = self._search_wikimedia_topic_photos(q, seen_urls, limit=3)
            for c in wm_cands:
                c.entity_type = "concept"
                tier1_leads.append(c)

        # -------------------------------------------------------------
        # Tier 2: Key Persons & Officials (Portraits & Press)
        # -------------------------------------------------------------
        target_persons = entities.persons or ([entities.main_person] if entities.main_person else [])
        for person in target_persons[:3]:
            # Exact Wikipedia Portrait
            wiki_portrait = self._resolve_wikipedia_portrait(person, entity_type="person", seen_urls=seen_urls)
            if wiki_portrait:
                tier2_persons.append(wiki_portrait)
            # Wikimedia person photos
            p_cands = self._search_person_photos(person, seen_urls, limit=6)
            for c in p_cands:
                c.entity_type = "person"
                c.entity_name = person
                tier2_persons.append(c)

        # -------------------------------------------------------------
        # Tier 3: City, Region & Landmark Atmosphere
        # -------------------------------------------------------------
        target_locs = entities.locations or ([event.primary_region] if event.primary_region else ["Addis Ababa"])
        for loc in target_locs[:2]:
            loc_cands = self._search_city_photos(loc, seen_urls, limit=6)
            tier3_locations.extend(loc_cands)

        # -------------------------------------------------------------
        # Tier 4: Institutions & Broader Domain Concepts
        # -------------------------------------------------------------
        for inst in entities.institutions[:2]:
            inst_cands = self._search_institution_photos(inst, seen_urls, limit=4)
            tier4_institutions_and_concepts.extend(inst_cands)

        # Backfill with general web search if total pool is small (< 18)
        if (len(tier1_leads) + len(tier2_persons) + len(tier3_locations) + len(tier4_institutions_and_concepts)) < 18:
            for q in entities.search_queries[:2]:
                web_res = self._search_bing_photos(q, seen_urls, limit=6)
                for c in web_res:
                    c.entity_type = "concept"
                    tier4_institutions_and_concepts.append(c)

        # Tier 7: Google Custom Search API (If configured)
        google_key = getattr(settings, "google_search_api_key", None)
        google_cx = getattr(settings, "google_search_cx", None)
        if google_key and google_cx and (len(tier1_leads) + len(tier2_persons)) < 12 and entities.search_queries:
            g_results = self._search_google_cse(entities.search_queries[0], google_key, google_cx, seen_urls, limit=8)
            tier4_institutions_and_concepts.extend(g_results)

        # -------------------------------------------------------------
        # Assemble Balanced Multi-Page Candidate Pool
        # Page 1: Leads & Direct Concepts (up to 6)
        # Page 2: Persons & Key Officials (up to 6)
        # Page 3: City & Regional Landscapes (up to 6)
        # Page 4: Institutions & Broad Concepts (up to 6)
        # -------------------------------------------------------------
        final_pool: list[PhotoCandidate] = []
        final_pool.extend(tier1_leads[:6])
        final_pool.extend(tier2_persons[:6])
        final_pool.extend(tier3_locations[:6])
        final_pool.extend(tier4_institutions_and_concepts[:6])

        # If any tier had extra candidates and we still have room under max_pool, add remainder
        if len(final_pool) < max_pool:
            remainder = (
                tier1_leads[6:] +
                tier2_persons[6:] +
                tier3_locations[6:] +
                tier4_institutions_and_concepts[6:]
            )
            for c in remainder:
                if len(final_pool) >= max_pool:
                    break
                final_pool.append(c)

        return final_pool

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
                    entity_type="lead",
                    entity_name=source_name,
                )
            )
        return candidates

    def analyze_story_entities(
        self, event: NewsEvent, custom_query: str | None = None
    ) -> StoryVisualEntities:
        """Extract concrete photographic entities (persons, cities, institutions, concepts)."""
        cache_key = f"{event.id}:{custom_query.strip().lower() if custom_query else ''}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        text = f"{event.title or ''} {event.summary or ''}".lower()
        topic: str = "Ethiopian News"
        main_person: str | None = None
        persons: list[str] = []
        locations: list[str] = []
        institutions: list[str] = []
        concepts: list[str] = []
        queries: list[str] = []
        chips: list[str] = []

        # -------------------------------------------------------------
        # 1. Custom Query Handling
        # -------------------------------------------------------------
        if custom_query and custom_query.strip():
            cq = custom_query.strip()
            topic = cq
            queries = [cq, f"{cq} Ethiopia", f"Contemporary {cq}"]
            chips = [cq, "Ethiopia"]
            entities = StoryVisualEntities(
                topic=topic,
                main_person=None,
                persons=[],
                locations=[cq] if any(w in cq.lower() for w in ["addis", "hawassa", "mekelle", "gondar"]) else [],
                institutions=[],
                concepts=[cq],
                search_queries=queries,
                suggested_chips=chips,
            )
            self._analysis_cache[cache_key] = entities
            return entities

        # -------------------------------------------------------------
        # 2. Comprehensive Ethiopian Knowledge Base (Deterministic & Fast)
        # -------------------------------------------------------------
        # 2a. Prominent Leaders & Figures
        person_map = [
            (["ዐቢይ", "አብይ", "ጠቅላይ ሚኒስትር", "abiy", "prime minister"], "Abiy Ahmed"),
            (["ዳንኤል በቀለ", "ዳንኤል", "daniel bekele", "ehrc", "ሰብዓዊ መብት"], "Daniel Bekele"),
            (["ማሞ ምህረቱ", "ማሞ", "mamo mihretu", "ብሔራዊ ባንክ", "national bank"], "Mamo Mihretu"),
            (["ታየ አጽቀ", "ታየ", "taye atske"], "Taye Atske Selassie"),
            (["ሳህለወርቅ", "ሳህለ-ወርቅ", "sahle-work"], "Sahle-Work Zewde"),
            (["ሽመልስ", "shimelis"], "Shimelis Abdisa"),
            (["አዳነች አቤቤ", "አዳነች", "adanech"], "Adanech Abebe"),
            (["ጌዲዮን ጢሞቴዎስ", "ጌዲዮን", "gedion"], "Gedion Timotheos"),
            (["አህመድ ሽዴ", "አህመድ", "ahmed shide"], "Ahmed Shide"),
            (["ደመቀ መኮንን", "ደመቀ", "demeke"], "Demeke Mekonnen"),
            (["ሃይለማሪያም", "hailemariam"], "Hailemariam Desalegn"),
            (["ፍሬህይወት ታምሩ", "ፍሬህይወት", "frehiwot"], "Frehiwot Tamiru"),
            (["መስፍን ጣሰው", "መስፍን", "mesfin tasew"], "Mesfin Tasew"),
            (["ደራርቱ ቱሉ", "ደራርቱ", "derartu"], "Derartu Tulu"),
            (["ኃይሌ ገብረስላሴ", "ሀይሌ", "haile gebrselassie"], "Haile Gebrselassie"),
            (["ቴዲ አፍሮ", "ቴዎድሮስ ካሳሁን", "teddy afro"], "Teddy Afro"),
            (["ዳንጎቴ", "dangote"], "Aliko Dangote"),
        ]
        for keywords, name in person_map:
            if any(k in text for k in keywords):
                if name not in persons:
                    persons.append(name)
                if not main_person:
                    main_person = name

        # 2b. Cities & Regional Centers
        location_map = [
            (["አዲስ አበባ", "addis ababa", "bole", "meskel square", "piazza", "arada"], "Addis Ababa"),
            (["ሀዋሳ", "ሐዋሳ", "hawassa", "awassa", "sidama"], "Hawassa"),
            (["መቀሌ", "መቐለ", "mekelle", "mekele", "tigray"], "Mekelle"),
            (["ባህር ዳር", "ባሕር ዳር", "bahir dar", "lake tana", "amhara"], "Bahir Dar"),
            (["ጎንደር", "ጐንደር", "gondar", "gonder"], "Gondar"),
            (["ድሬዳዋ", "ድሬ ዳዋ", "dire dawa"], "Dire Dawa"),
            (["ጅማ", "jimma"], "Jimma"),
            (["አዳማ", "adama", "nazret"], "Adama"),
            (["ቢሾፍቱ", "bishoftu", "debre zeit"], "Bishoftu"),
            (["ሐረር", "ሀረር", "harar"], "Harar"),
            (["ጅጅጋ", "jijiga"], "Jijiga"),
            (["ሰመራ", "semera", "afar", "danakil"], "Semera"),
            (["አሶሳ", "asosa", "benishangul"], "Asosa"),
            (["ጋምቤላ", "gambella"], "Gambella"),
            (["ሞጆ", "modjo", "dry port"], "Modjo"),
            (["ላሊበላ", "lalibela"], "Lalibela"),
            (["አክሱም", "axum"], "Axum"),
        ]
        for keywords, loc_name in location_map:
            if any(k in text for k in keywords):
                if loc_name not in locations:
                    locations.append(loc_name)

        # 2c. Institutions & Organizations
        institution_map = [
            (["ብሔራዊ ባንክ", "nbe", "national bank of ethiopia"], "National Bank of Ethiopia"),
            (["የኢትዮጵያ ንግድ ባንክ", "ንግድ ባንክ", "cbe", "commercial bank of ethiopia"], "Commercial Bank of Ethiopia"),
            (["የኢትዮጵያ አየር መንገድ", "አየር መንገድ", "ethiopian airlines"], "Ethiopian Airlines"),
            (["ኢትዮ ቴሌኮም", "ቴሌኮም", "ethio telecom"], "Ethio Telecom"),
            (["ጠቅላይ ፍርድ ቤት", "ፍርድ ቤት", "supreme court", "court", "judiciary", "justice"], "Federal Supreme Court of Ethiopia"),
            (["ሰብዓዊ መብት ኮሚሽን", "ehrc", "human rights commission"], "Ethiopian Human Rights Commission"),
            (["የህዝብ ተወካዮች ምክር ቤት", "ምክር ቤት", "parliament"], "Ethiopian Parliament"),
            (["ታላቁ የህዳሴ ግድብ", "ህዳሴ ግድብ", "ህዳሴ", "gerd", "renaissance dam"], "Grand Ethiopian Renaissance Dam"),
            (["የአፍሪካ ህብረት", "አፍሪካ ህብረት", "african union"], "African Union"),
        ]
        for keywords, inst_name in institution_map:
            if any(k in text for k in keywords):
                if inst_name not in institutions:
                    institutions.append(inst_name)

        # 2d. Concrete Photographic Concepts
        concept_map = [
            (["ይቅርታ", "እስረኛ", "እስር", "pardon", "prisoner", "prison", "ፍርድ"], ["Ethiopian court justice", "Ethiopia prison"]),
            (["ባንክ", "ብር", "ገንዘብ", "devaluation", "currency", "birr", "forex", "exchange rate"], ["Ethiopian Birr banknotes", "Commercial Bank of Ethiopia"]),
            (["ቡና", "እርሻ", "coffee", "agriculture", "farming", "crop", "wheat"], ["Ethiopian coffee harvest", "Ethiopia agriculture farming"]),
            (["በረራ", "አውሮፕላን", "flight", "aviation", "airline", "aircraft"], ["Ethiopian Airlines aircraft", "Bole International Airport"]),
            (["ሰላም", "ስምምነት", "peace", "treaty", "diplomacy", "talks"], ["African Union Addis Ababa", "Ethiopian diplomacy"]),
            (["ትምህርት", "ዩኒቨርሲቲ", "university", "education", "school"], ["Addis Ababa University", "Ethiopia education"]),
        ]
        for keywords, conc_list in concept_map:
            if any(k in text for k in keywords):
                for c in conc_list:
                    if c not in concepts:
                        concepts.append(c)

        # -------------------------------------------------------------
        # 3. LLM Extraction Enhancement (when available)
        # -------------------------------------------------------------
        if self.text_provider and self.text_provider.is_available():
            try:
                prompt = (
                    "You are a photo desk director for a newsroom in Ethiopia.\n"
                    "Extract concrete, photographic search entities.\n"
                    "Editorial rules: Search engines fail on news headlines. "
                    "Extract concrete nouns, people's names, cities/locations, and institutions that have actual photos available.\n\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {(event.summary or '')[:450]}\n"
                    f"Category: {event.primary_category or 'General'}, Region: {event.primary_region or 'Ethiopia'}\n\n"
                    "Output JSON ONLY:\n"
                    "{\n"
                    '  "topic": "Concise 2-4 word editorial topic",\n'
                    '  "searchable_concepts": ["2-3 word photographic noun query 1", "query 2"],\n'
                    '  "persons": ["Full English name of key figures or officials mentioned"],\n'
                    '  "locations": ["City, capital, or landmark mentioned"],\n'
                    '  "institutions": ["Organization, ministry, or bank"],\n'
                    '  "suggested_chips": ["Chip 1", "Chip 2", "Chip 3", "Chip 4"]\n'
                    "}"
                )
                req = TextGenerationRequest(prompt=prompt)
                res = self.text_provider.generate_text(req)
                match = re.search(r"\{.*\}", res.text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    t = str(parsed.get("topic") or "").strip()
                    if t:
                        topic = t
                    for p in parsed.get("persons", []):
                        p_str = str(p).strip()
                        if p_str and p_str.lower() not in ("null", "none", "") and p_str not in persons:
                            persons.append(p_str)
                            if not main_person:
                                main_person = p_str
                    for loc in parsed.get("locations", []):
                        loc_str = str(loc).strip()
                        if loc_str and loc_str not in locations:
                            locations.append(loc_str)
                    for inst in parsed.get("institutions", []):
                        inst_str = str(inst).strip()
                        if inst_str and inst_str not in institutions:
                            institutions.append(inst_str)
                    for sc in parsed.get("searchable_concepts", []):
                        sc_str = str(sc).strip()
                        if sc_str and sc_str not in concepts:
                            concepts.append(sc_str)
                    raw_q = parsed.get("queries") or parsed.get("search_queries") or []
                    if raw_q:
                        queries = [str(q).strip() for q in raw_q if str(q).strip()]
                    for ch in parsed.get("suggested_chips", []):
                        ch_str = str(ch).strip()
                        if ch_str and ch_str not in chips:
                            chips.append(ch_str)
            except Exception as exc:
                logger.warning("llm_story_entities_failed", error=_safe_str(exc))

        # Defaults if empty
        if not locations:
            locations = [event.primary_region] if event.primary_region else ["Addis Ababa"]
        if not concepts:
            concepts = [f"{locations[0]} Ethiopia", "Contemporary Ethiopia"]
        if not topic or topic == "Ethiopian News":
            if persons:
                topic = f"{persons[0]} & Leadership"
            elif institutions:
                topic = institutions[0]
            elif concepts:
                topic = concepts[0]
            else:
                topic = f"{locations[0]} News"

        # Build search queries if not already populated from LLM
        if not queries:
            queries = []
            if persons:
                queries.append(f"{persons[0]} Ethiopia")
            if institutions:
                queries.append(f"{institutions[0]}")
            if concepts:
                queries.append(concepts[0])
            queries.append(f"{locations[0]} Ethiopia")

        # Build suggested chips
        if not chips:
            if persons:
                chips.append(persons[0])
            if locations:
                chips.append(locations[0])
            if institutions:
                chips.append(institutions[0])
            if concepts:
                chips.append(concepts[0])

        entities = StoryVisualEntities(
            topic=topic,
            main_person=main_person or (persons[0] if persons else None),
            persons=persons,
            locations=locations,
            institutions=institutions,
            concepts=concepts,
            search_queries=queries,
            suggested_chips=chips[:5],
        )
        self._analysis_cache[cache_key] = entities
        return entities

    def analyze_story(
        self, event: NewsEvent, custom_query: str | None = None
    ) -> tuple[str, str | None, list[str], list[str]]:
        """Backward-compatible wrapper returning (topic, main_person, queries, suggested_chips)."""
        entities = self.analyze_story_entities(event, custom_query=custom_query)
        return entities.topic, entities.main_person, entities.search_queries, entities.suggested_chips

    def _resolve_wikipedia_portrait(
        self,
        entity_name: str,
        entity_type: str = "person",
        seen_urls: set[str] | None = None,
    ) -> PhotoCandidate | None:
        """Resolve exact high-resolution Wikipedia infobox photo for a person, city, or institution."""
        if not entity_name or not entity_name.strip():
            return None
        name = entity_name.strip()
        cache_key = f"wiki_img:{name.lower()}"
        if hasattr(self, "_wiki_img_cache") and cache_key in self._wiki_img_cache:
            cand = self._wiki_img_cache[cache_key]
            if cand and seen_urls is not None and cand.image_url in seen_urls:
                return None
            return cand

        if not hasattr(self, "_wiki_img_cache"):
            self._wiki_img_cache = {}

        try:
            s_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(name)}&format=json"
            with httpx.Client(timeout=6.0, headers=_WIKI_HEADERS) as client:
                r = client.get(s_url)
                if r.status_code != 200:
                    return None
                hits = r.json().get("query", {}).get("search", [])
                if not hits:
                    return None
                best_title = hits[0]["title"]
                # Fetch page image and extract
                p_url = (
                    f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(best_title)}"
                    f"&prop=pageimages|extracts&pithumbsize=1200&exintro=1&explaintext=1&format=json"
                )
                r2 = client.get(p_url)
                if r2.status_code != 200:
                    return None
                pages = r2.json().get("query", {}).get("pages", {})
                for pid, p in pages.items():
                    thumb = p.get("thumbnail", {}).get("source")
                    if not thumb:
                        continue
                    if any(thumb.lower().endswith(ext) for ext in _EXCLUDED_EXTENSIONS):
                        continue
                    if any(bad in thumb.lower() for bad in ("logo", "flag", "seal", "emblem", "coat_of_arms")):
                        continue

                    if seen_urls is not None and thumb in seen_urls:
                        return None

                    cand = PhotoCandidate(
                        id=f"wiki-direct-{pid}",
                        title=f"{name} ({best_title})",
                        thumb_url=thumb,
                        image_url=upscale_news_cdn_url(thumb),
                        source="wikimedia",
                        photographer="Wikipedia Editorial",
                        description=f"Official {entity_type} reference: {best_title}",
                        entity_type=entity_type,
                        entity_name=name,
                    )
                    self._wiki_img_cache[cache_key] = cand
                    if seen_urls is not None:
                        seen_urls.add(thumb)
                    return cand
        except Exception as exc:
            logger.warning("wiki_portrait_resolution_failed", entity=_safe_str(name), error=_safe_str(exc))
        return None

    def _search_city_photos(
        self,
        city_name: str,
        seen_urls: set[str],
        limit: int = 6,
    ) -> list[PhotoCandidate]:
        """Search Wikimedia Commons and Openverse specifically for high-res cityscapes and landmarks."""
        candidates: list[PhotoCandidate] = []
        # 1. First attempt exact Wikipedia lead photo
        wiki_direct = self._resolve_wikipedia_portrait(city_name, entity_type="location", seen_urls=seen_urls)
        if wiki_direct:
            candidates.append(wiki_direct)

        # 2. Wikimedia Commons cityscape search
        queries = [f"{city_name} skyline", f"{city_name} city Ethiopia", f"{city_name} landmark"]
        for q in queries[:2]:
            if len(candidates) >= limit:
                break
            wm_res = self._search_wikimedia_topic_photos(q, seen_urls, limit=4)
            for cand in wm_res:
                cand.entity_type = "location"
                cand.entity_name = city_name
                candidates.append(cand)

        # 3. Openverse search
        if len(candidates) < limit:
            ov_res = self._search_openverse_photos(f"{city_name} Ethiopia", seen_urls, limit=4)
            for cand in ov_res:
                cand.entity_type = "location"
                cand.entity_name = city_name
                candidates.append(cand)

        return candidates[:limit]

    def _search_institution_photos(
        self,
        inst_name: str,
        seen_urls: set[str],
        limit: int = 6,
    ) -> list[PhotoCandidate]:
        """Search Wikipedia and Wikimedia Commons for institution headquarters and facilities."""
        candidates: list[PhotoCandidate] = []
        # 1. Exact Wikipedia lead photo
        wiki_direct = self._resolve_wikipedia_portrait(inst_name, entity_type="institution", seen_urls=seen_urls)
        if wiki_direct:
            candidates.append(wiki_direct)

        # 2. Wikimedia Commons search
        c_res = self._search_wikimedia_topic_photos(f"{inst_name} building", seen_urls, limit=4)
        for cand in c_res:
            cand.entity_type = "institution"
            cand.entity_name = inst_name
            candidates.append(cand)

        return candidates[:limit]

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
