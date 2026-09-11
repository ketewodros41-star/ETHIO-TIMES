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


def _match_kw(keyword: str, haystack: str) -> bool:
    if len(keyword) <= 6 and keyword.isascii() and " " not in keyword:
        return bool(re.search(rf"\b{re.escape(keyword)}\b", haystack))
    return keyword in haystack


def clean_entity_name(s: str) -> str:
    return re.sub(r"^(Former|The|An|A)\s+", "", s, flags=re.IGNORECASE).strip()


def _is_name_subsumed(new_name: str, existing_names: list[str]) -> bool:
    import unicodedata
    def norm(s: str) -> str:
        s = clean_entity_name(s)
        s_ascii = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
        return re.sub(r"[^a-z0-9]", "", s_ascii.lower())
    n_new = norm(new_name)
    for ext in existing_names:
        n_ext = norm(ext)
        if n_new == n_ext or (len(n_new) >= 5 and n_new in n_ext) or (len(n_ext) >= 5 and n_ext in n_new):
            return True
    return False


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
    country: str = "Ethiopia"
    country_code: str = "ET"
    default_city: str = "Addis Ababa"
    main_person: str | None = None
    persons: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    suggested_chips: list[str] = field(default_factory=list)


class WebImageScraper:
    """Multi-source free web image scraper tailored for news stories."""

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
        # Entity & Story Analysis (LLM + Multi-Country Context Knowledge Base)
        # -------------------------------------------------------------
        entities = self.analyze_story_entities(event, custom_query=custom_query)

        logger.info(
            "web_image_search_plan",
            event_id=str(event.id),
            country=entities.country,
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
        target_locs = [loc for loc in (entities.locations or ([entities.default_city] if entities.default_city else [])) if loc]
        for loc in target_locs[:2]:
            loc_cands = self._search_city_photos(
                loc,
                seen_urls,
                limit=6,
                country_context=entities.country,
            )
            tier3_locations.extend(loc_cands)

        # -------------------------------------------------------------
        # Tier 4: Institutions & Broader Domain Concepts
        # -------------------------------------------------------------
        for inst in entities.institutions[:2]:
            inst_cands = self._search_institution_photos(
                inst,
                seen_urls,
                limit=4,
                country_context=entities.country,
            )
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

            try:
                source_name = getattr(art.source, "name", "News Source") if hasattr(art, "source") and art.source else "Original Story"
            except Exception:
                source_name = "Original Story"
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

    def _detect_country_and_context(self, event: NewsEvent) -> dict:
        """Detect the primary geographic & national context for the news event."""
        text = f"{event.title or ''} {event.summary or ''}".lower()
        region = (event.primary_region or "").lower()

        scores: dict[str, int] = {
            "US": 0,
            "ET": 0,
            "KE": 0,
            "SD": 0,
            "SO": 0,
            "YE": 0,
            "GB": 0,
            "EG": 0,
            "CN": 0,
            "ZA": 0,
        }

        # 1. US indicators
        us_strong = [
            "pentagon", "white house", "us capitol", "u.s. capitol", "us congress", "u.s. congress",
            "federal reserve", "wall street", "biden", "trump", "kamala", "blinken", "lloyd austin",
            "centcom", "us military", "u.s. military", "us department of defense", "us strike",
            "american strike", "us air force", "us navy", "american president", "us election"
        ]
        us_med = ["united states", "america", "american", "washington", "new york", "california", "texas", "us dollar"]
        for k in us_strong:
            if _match_kw(k, text):
                scores["US"] += 4
        for k in us_med:
            if _match_kw(k, text):
                scores["US"] += 2
        for short in ("u.s.", "usa", "us"):
            if re.search(rf"\b{re.escape(short)}\b", text):
                scores["US"] += 2

        # 2. Ethiopia indicators
        et_strong = [
            "ዐቢይ", "አብይ", "abiy", "temesgen", "daniel bekele", "mamo mihretu", "gerd", "cbe", "nbe",
            "ethiopian airlines", "amhara", "oromia", "tigray", "addis ababa", "ethio telecom",
            "federal supreme court of ethiopia", "commercial bank of ethiopia", "renaissance dam"
        ]
        et_med = ["ethiopia", "ethiopian", "birr", "ena", "habesha"]
        for k in et_strong:
            if _match_kw(k, text):
                scores["ET"] += 4
        for k in et_med:
            if _match_kw(k, text):
                # If "ethiopian migrants" or "ethiopian civilians" is mentioned as collateral victims in foreign strikes, discount weight
                if re.search(r"ethiopian\s+(migrants|victims|civilians|passengers|refugees|nationals)", text):
                    scores["ET"] += 1
                else:
                    scores["ET"] += 2

        # 3. Yemen indicators
        ye_strong = ["yemen", "yemeni", "sanaa", "houthi", "houthis", "aden", "red sea shipping"]
        for k in ye_strong:
            if _match_kw(k, text):
                scores["YE"] += 3

        # 4. Kenya indicators
        ke_strong = ["kenya", "kenyan", "nairobi", "ruto", "william ruto", "mombasa"]
        for k in ke_strong:
            if _match_kw(k, text):
                scores["KE"] += 3

        # 5. Sudan indicators
        sd_strong = ["sudan", "sudanese", "khartoum", "burhan", "hemeti", "rapid support forces", "port sudan"]
        for k in sd_strong:
            if _match_kw(k, text):
                scores["SD"] += 3

        # 6. Somalia indicators
        so_strong = ["somalia", "somali", "mogadishu", "hassan sheikh", "somaliland", "hargeisa"]
        for k in so_strong:
            if _match_kw(k, text):
                scores["SO"] += 3

        # 7. UK indicators
        gb_strong = ["united kingdom", "britain", "british", "london", "downing street", "westminster", "starmer", "sunak"]
        for k in gb_strong:
            if _match_kw(k, text):
                scores["GB"] += 3

        # 8. Egypt indicators
        eg_strong = ["egypt", "egyptian", "cairo", "sisi", "el-sisi", "suez canal", "alexandria"]
        for k in eg_strong:
            if _match_kw(k, text):
                scores["EG"] += 3

        # 9. China indicators
        cn_strong = ["china", "chinese", "beijing", "xi jinping", "shanghai"]
        for k in cn_strong:
            if _match_kw(k, text):
                scores["CN"] += 3

        # 10. South Africa indicators
        za_strong = ["south africa", "south african", "johannesburg", "cape town", "pretoria", "ramaphosa"]
        for k in za_strong:
            if _match_kw(k, text):
                scores["ZA"] += 3

        # Check explicit region if provided
        if region:
            if "ethiopia" in region:
                scores["ET"] += 3
            elif any(w in region for w in ["united states", "america", "usa", "us"]):
                scores["US"] += 3
            elif "kenya" in region:
                scores["KE"] += 3
            elif "sudan" in region:
                scores["SD"] += 3
            elif "somalia" in region:
                scores["SO"] += 3
            elif "yemen" in region:
                scores["YE"] += 3
            elif "uk" in region or "britain" in region:
                scores["GB"] += 3
            elif "china" in region:
                scores["CN"] += 3
            elif "egypt" in region:
                scores["EG"] += 3
            elif "south africa" in region:
                scores["ZA"] += 3

        # Decide top country
        top_code = None
        top_score = 0
        for code, s in scores.items():
            if s > top_score:
                top_code = code
                top_score = s

        # CRITICAL: If no explicit country indicators matched (e.g. sports, entertainment, global news),
        # NEVER default to Ethiopia! Designate as Global / International.
        if top_score == 0 or top_code is None:
            return {
                "country": "Global",
                "country_code": "GLOBAL",
                "default_city": "",
                "default_institutions": [],
                "default_concepts": [],
            }

        profiles = {
            "US": {
                "country": "United States",
                "country_code": "US",
                "default_city": "Washington, D.C.",
                "default_institutions": ["The Pentagon", "White House", "United States Capitol"],
                "default_concepts": ["The Pentagon building", "US Department of Defense", "Washington D.C."],
            },
            "ET": {
                "country": "Ethiopia",
                "country_code": "ET",
                "default_city": "Addis Ababa",
                "default_institutions": ["Commercial Bank of Ethiopia", "Ethiopian Airlines", "National Bank of Ethiopia"],
                "default_concepts": ["Addis Ababa Ethiopia", "Contemporary Ethiopia"],
            },
            "YE": {
                "country": "Yemen",
                "country_code": "YE",
                "default_city": "Sanaa",
                "default_institutions": ["Sanaa Old City"],
                "default_concepts": ["Sanaa Yemen", "Yemen landscape"],
            },
            "KE": {
                "country": "Kenya",
                "country_code": "KE",
                "default_city": "Nairobi",
                "default_institutions": ["State House Kenya", "Parliament of Kenya"],
                "default_concepts": ["Nairobi skyline", "Nairobi Kenya"],
            },
            "SD": {
                "country": "Sudan",
                "country_code": "SD",
                "default_city": "Khartoum",
                "default_institutions": ["Port Sudan", "Khartoum Nile"],
                "default_concepts": ["Khartoum Sudan", "Sudan Red Sea"],
            },
            "SO": {
                "country": "Somalia",
                "country_code": "SO",
                "default_city": "Mogadishu",
                "default_institutions": ["Villa Somalia", "Mogadishu port"],
                "default_concepts": ["Mogadishu Somalia", "Mogadishu coast"],
            },
            "GB": {
                "country": "United Kingdom",
                "country_code": "GB",
                "default_city": "London",
                "default_institutions": ["10 Downing Street", "Palace of Westminster"],
                "default_concepts": ["London skyline", "Westminster London"],
            },
            "EG": {
                "country": "Egypt",
                "country_code": "EG",
                "default_city": "Cairo",
                "default_institutions": ["Cairo Nile", "Suez Canal"],
                "default_concepts": ["Cairo Egypt", "Cairo skyline"],
            },
            "CN": {
                "country": "China",
                "country_code": "CN",
                "default_city": "Beijing",
                "default_institutions": ["Great Hall of the People"],
                "default_concepts": ["Beijing China", "Shanghai skyline"],
            },
            "ZA": {
                "country": "South Africa",
                "country_code": "ZA",
                "default_city": "Johannesburg",
                "default_institutions": ["Union Buildings Pretoria"],
                "default_concepts": ["Johannesburg skyline", "Cape Town Table Mountain"],
            },
        }

        return profiles.get(top_code, {
            "country": "Global",
            "country_code": "GLOBAL",
            "default_city": "",
            "default_institutions": [],
            "default_concepts": [],
        })

    def analyze_story_entities(
        self, event: NewsEvent, custom_query: str | None = None
    ) -> StoryVisualEntities:
        """Extract concrete photographic entities (persons, cities, institutions, concepts)."""
        cache_key = f"{event.id}:{custom_query.strip().lower() if custom_query else ''}"
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        text = f"{event.title or ''} {event.summary or ''}".lower()
        ctx = self._detect_country_and_context(event)
        country = ctx["country"]
        country_code = ctx["country_code"]
        default_city = ctx["default_city"]

        topic: str = f"{country} News"
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
            is_et_query = any(w in cq.lower() for w in ["ethiopia", "addis", "hawassa", "mekelle", "gondar", "amhara", "oromia", "tigray"])
            is_us_query = any(w in cq.lower() for w in ["pentagon", "white house", "washington", "biden", "trump", "america", "united states", "congress"])

            if is_us_query or (country_code == "US" and not is_et_query):
                queries = [cq, f"{cq} United States", f"{cq} building" if any(b in cq.lower() for b in ["pentagon", "capitol", "house", "department"]) else f"{cq} official"]
                chips = [cq, "United States", "Washington D.C."]
                locs = [cq] if any(w in cq.lower() for w in ["washington", "york", "pentagon"]) else ["Washington, D.C."]
            elif is_et_query or (country_code == "ET" and not is_us_query):
                queries = [cq, f"{cq} Ethiopia", f"Contemporary {cq}"]
                chips = [cq, "Ethiopia"]
                locs = [cq] if any(w in cq.lower() for w in ["addis", "hawassa", "mekelle", "gondar"]) else ["Addis Ababa"]
            else:
                queries = [cq, f"{cq} {country}", f"{cq} news"]
                chips = [cq, country]
                locs = [cq]

            entities = StoryVisualEntities(
                topic=topic,
                country=country,
                country_code=country_code,
                default_city=default_city,
                main_person=None,
                persons=[],
                locations=locs,
                institutions=[cq] if any(w in cq.lower() for w in ["pentagon", "bank", "ministry", "house", "capitol", "department"]) else [],
                concepts=[cq],
                search_queries=queries,
                suggested_chips=chips,
            )
            self._analysis_cache[cache_key] = entities
            return entities

        # -------------------------------------------------------------
        # 2. Multi-Country Knowledge Base (Deterministic & Fast)
        # -------------------------------------------------------------
        # 2a. Prominent Leaders, Icons & Figures (Ethiopian + Global Sports/Tech/World)
        person_map = [
            # Ethiopian figures
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
            # Global Football & Sports Icons
            (["kylian mbappe", "kylian mbappé", "mbappe", "mbappé"], "Kylian Mbappé"),
            (["ryan giggs", "giggs"], "Ryan Giggs"),
            (["lionel messi", "messi", "leo messi"], "Lionel Messi"),
            (["cristiano ronaldo", "ronaldo", "cr7"], "Cristiano Ronaldo"),
            (["erling haaland", "haaland"], "Erling Haaland"),
            (["mohamed salah", "mo salah", "salah"], "Mohamed Salah"),
            (["vinicius junior", "vinicius jr", "vinicius"], "Vinicius Junior"),
            (["jude bellingham", "bellingham"], "Jude Bellingham"),
            (["harry kane", "kane"], "Harry Kane"),
            (["neymar", "neymar jr"], "Neymar"),
            (["alex ferguson", "ferguson", "sir alex"], "Alex Ferguson"),
            (["pep guardiola", "guardiola"], "Pep Guardiola"),
            (["jurgen klopp", "klopp"], "Jurgen Klopp"),
            (["mikel arteta", "arteta"], "Mikel Arteta"),
            (["erik ten hag", "ten hag"], "Erik ten Hag"),
            (["carlo ancelotti", "ancelotti"], "Carlo Ancelotti"),
            (["jose mourinho", "mourinho"], "Jose Mourinho"),
            (["lebron james", "lebron"], "LeBron James"),
            (["stephen curry", "steph curry", "curry"], "Stephen Curry"),
            (["giannis antetokounmpo", "giannis"], "Giannis Antetokounmpo"),
            (["novak djokovic", "djokovic"], "Novak Djokovic"),
            (["carlos alcaraz", "alcaraz"], "Carlos Alcaraz"),
            (["lewis hamilton", "hamilton"], "Lewis Hamilton"),
            (["max verstappen", "verstappen"], "Max Verstappen"),
            # Global Business & Tech Icons
            (["elon musk", "musk"], "Elon Musk"),
            (["satya nadella", "nadella"], "Satya Nadella"),
            (["sundar pichai", "pichai"], "Sundar Pichai"),
            (["sam altman", "altman"], "Sam Altman"),
            (["mark zuckerberg", "zuckerberg"], "Mark Zuckerberg"),
            (["jeff bezos", "bezos"], "Jeff Bezos"),
            (["bill gates", "gates"], "Bill Gates"),
            (["tim cook"], "Tim Cook"),
            (["jensen huang"], "Jensen Huang"),
            # International & Political figures
            (["joe biden", "biden", "president biden"], "Joe Biden"),
            (["donald trump", "trump"], "Donald Trump"),
            (["kamala harris", "kamala"], "Kamala Harris"),
            (["antony blinken", "blinken", "secretary blinken"], "Antony Blinken"),
            (["lloyd austin", "austin", "defense secretary"], "Lloyd Austin"),
            (["jerome powell", "powell", "fed chair"], "Jerome Powell"),
            (["jd vance", "vance"], "JD Vance"),
            (["william ruto", "ruto"], "William Ruto"),
            (["abdel fattah al-burhan", "burhan", "al-burhan"], "Abdel Fattah al-Burhan"),
            (["hassan sheikh mohamud", "hassan sheikh"], "Hassan Sheikh Mohamud"),
            (["keir starmer", "starmer"], "Keir Starmer"),
            (["rishi sunak", "sunak"], "Rishi Sunak"),
            (["emmanuel macron", "macron"], "Emmanuel Macron"),
            (["volodymyr zelenskyy", "zelenskyy", "zelensky"], "Volodymyr Zelenskyy"),
            (["vladimir putin", "putin"], "Vladimir Putin"),
            (["benjamin netanyahu", "netanyahu"], "Benjamin Netanyahu"),
            (["antónio guterres", "guterres"], "António Guterres"),
        ]
        for keywords, name in person_map:
            matched = False
            for k in keywords:
                if len(k) <= 6 and k.isascii():
                    if re.search(rf"\b{re.escape(k)}\b", text):
                        matched = True
                        break
                elif k in text:
                    matched = True
                    break
            if matched:
                if name not in persons:
                    persons.append(name)
                if not main_person:
                    main_person = name

        # 2b. Cities & Regional Centers
        location_map = [
            # Ethiopian cities
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
            # International & US locations
            (["the pentagon", "pentagon"], "The Pentagon"),
            (["washington", "washington d.c.", "washington dc", "d.c."], "Washington, D.C."),
            (["new york", "nyc", "manhattan"], "New York City"),
            (["california", "los angeles"], "California"),
            (["texas", "houston", "austin"], "Texas"),
            (["yemen", "sanaa", "aden", "hodeidah"], "Yemen"),
            (["nairobi", "kenya", "mombasa"], "Nairobi"),
            (["khartoum", "sudan", "port sudan"], "Khartoum"),
            (["mogadishu", "somalia", "hargeisa", "somaliland"], "Mogadishu"),
            (["london", "united kingdom", "westminster"], "London"),
            (["manchester", "old trafford"], "Manchester"),
            (["madrid", "santiago bernabeu"], "Madrid"),
            (["barcelona", "camp nou"], "Barcelona"),
            (["paris", "parc des princes"], "Paris"),
            (["munich", "allianz arena"], "Munich"),
            (["milan", "san siro"], "Milan"),
            (["cairo", "egypt"], "Cairo"),
            (["beijing", "china"], "Beijing"),
            (["johannesburg", "south africa", "pretoria", "cape town"], "Johannesburg"),
            (["gaza", "rafah"], "Gaza"),
            (["beirut", "lebanon"], "Beirut"),
        ]

        for keywords, loc_name in location_map:
            if any(_match_kw(k, text) for k in keywords):
                if loc_name not in locations:
                    locations.append(loc_name)

        # 2c. Institutions, Sports Clubs & Organizations
        institution_map = [
            # Ethiopian institutions
            (["ብሔራዊ ባንክ", "nbe", "national bank of ethiopia"], "National Bank of Ethiopia"),
            (["የኢትዮጵያ ንግድ ባንክ", "ንግድ ባንክ", "cbe", "commercial bank of ethiopia"], "Commercial Bank of Ethiopia"),
            (["የኢትዮጵያ አየር መንገድ", "አየር መንገድ", "ethiopian airlines"], "Ethiopian Airlines"),
            (["ኢትዮ ቴሌኮም", "ቴሌኮም", "ethio telecom"], "Ethio Telecom"),
            (["ጠቅላይ ፍርድ ቤት", "ፍርድ ቤት", "supreme court", "court", "judiciary", "justice"], "Federal Supreme Court of Ethiopia"),
            (["ሰብዓዊ መብት ኮሚሽን", "ehrc", "human rights commission"], "Ethiopian Human Rights Commission"),
            (["የህዝብ ተወካዮች ምክር ቤት", "ምክር ቤት", "parliament"], "Ethiopian Parliament"),
            (["ታላቁ የህዳሴ ግድብ", "ህዳሴ ግድብ", "ህዳሴ", "gerd", "renaissance dam"], "Grand Ethiopian Renaissance Dam"),
            (["የአፍሪካ ህብረት", "አፍሪካ ህብረት", "african union"], "African Union"),
            # Global Football Clubs & Sports Organizations
            (["manchester united", "man utd", "manchester utd", "mufc", "red devils"], "Manchester United F.C."),
            (["real madrid", "los blancos"], "Real Madrid CF"),
            (["fc barcelona", "barcelona", "barca", "barça", "blaugrana"], "FC Barcelona"),
            (["arsenal", "arsenal fc", "the gunners"], "Arsenal F.C."),
            (["liverpool", "liverpool fc", "the reds"], "Liverpool F.C."),
            (["chelsea", "chelsea fc", "the blues"], "Chelsea F.C."),
            (["manchester city", "man city", "mcfc"], "Manchester City F.C."),
            (["bayern munich", "fc bayern", "bayern"], "FC Bayern Munich"),
            (["paris saint-germain", "psg", "paris sg"], "Paris Saint-Germain F.C."),
            (["juventus", "juve"], "Juventus FC"),
            (["inter milan", "internazionale"], "Inter Milan"),
            (["ac milan", "rossoneri"], "AC Milan"),
            (["tottenham", "tottenham hotspur", "spurs"], "Tottenham Hotspur F.C."),
            (["borussia dortmund", "dortmund", "bvb"], "Borussia Dortmund"),
            (["fifa"], "FIFA"),
            (["uefa", "uefa champions league", "champions league"], "UEFA"),
            (["premier league", "epl", "english premier league"], "Premier League"),
            (["la liga"], "La Liga"),
            (["serie a"], "Serie A"),
            (["bundesliga"], "Bundesliga"),
            (["nba", "national basketball association"], "NBA"),
            (["formula 1", "formula one", "f1"], "Formula 1"),
            # Global Tech & Corporate Institutions
            (["apple", "apple inc"], "Apple Inc."),
            (["microsoft"], "Microsoft"),
            (["google", "alphabet"], "Google"),
            (["tesla"], "Tesla, Inc."),
            (["openai"], "OpenAI"),
            (["meta platforms", "meta"], "Meta Platforms"),
            (["amazon"], "Amazon (company)"),
            (["nvidia"], "Nvidia"),
            (["spacex"], "SpaceX"),
            # International & US institutions
            (["the pentagon", "pentagon", "department of defense", "defense department", "dod"], "The Pentagon"),
            (["white house"], "White House"),
            (["capitol", "us capitol", "congress", "us congress", "senate", "house of representatives"], "United States Capitol"),
            (["federal reserve", "fed"], "Federal Reserve"),
            (["supreme court of the united states", "us supreme court"], "Supreme Court of the United States"),
            (["wall street", "new york stock exchange", "nyse"], "Wall Street"),
            (["centcom", "us military", "u.s. military", "us central command"], "United States Armed Forces"),
            (["united nations", "un security council", "unsc"], "United Nations"),
            (["imf", "international monetary fund"], "International Monetary Fund"),
            (["world bank"], "World Bank"),
            (["who", "world health organization"], "World Health Organization"),
            (["nato", "north atlantic treaty organization"], "NATO"),
        ]
        for keywords, inst_name in institution_map:
            if any(_match_kw(k, text) for k in keywords):
                if not _is_name_subsumed(inst_name, institutions):
                    institutions.append(inst_name)

        # 2d. Concrete Photographic Concepts
        concept_map = [
            # Ethiopian concepts
            (["ይቅርታ", "እስረኛ", "እስር", "pardon", "prisoner", "prison", "ፍርድ"], ["Ethiopian court justice", "Ethiopia prison"]),
            (["ባንክ", "ብር", "ገንዘብ", "devaluation", "currency", "birr", "forex", "exchange rate"], ["Ethiopian Birr banknotes", "Commercial Bank of Ethiopia"]),
            (["ቡና", "እርሻ", "coffee", "agriculture", "farming", "crop", "wheat"], ["Ethiopian coffee harvest", "Ethiopia agriculture farming"]),
            (["በረራ", "አውሮፕላን", "flight", "aviation", "airline", "aircraft"], ["Ethiopian Airlines aircraft", "Bole International Airport"]),
            (["ሰላም", "ስምምነት", "peace", "treaty", "diplomacy", "talks"], ["African Union Addis Ababa", "Ethiopian diplomacy"]),
            (["ትምህርት", "ዩኒቨርሲቲ", "university", "education", "school"], ["Addis Ababa University", "Ethiopia education"]),
            # Sports & Entertainment concepts
            (["football", "soccer", "champions league", "premier league", "match", "scouted", "transfer", "derby", "stadium", "striker", "coach", "teenage"], ["Football stadium match", "Soccer training session", "Premier League football"]),
            (["basketball", "nba", "playoffs", "slam dunk"], ["NBA basketball arena", "Basketball game action"]),
            (["formula 1", "f1", "grand prix", "racing car"], ["Formula 1 racing circuit", "F1 Grand Prix race"]),
            (["tennis", "grand slam", "wimbledon"], ["Grand Slam tennis court", "Tennis match tournament"]),
            (["artificial intelligence", "ai", "machine learning", "silicon valley"], ["Silicon Valley technology", "Artificial Intelligence tech"]),
            # US & International concepts
            (["pentagon", "strike", "airstrike", "drone strike", "civilian deaths", "military operation", "centcom"], ["The Pentagon building", "US Department of Defense press briefing", "Military aircraft"]),
            (["us election", "presidential election", "campaign", "ballot", "republican", "democrat"], ["United States presidential election", "United States Capitol"]),
            (["wall street", "stock market", "inflation", "interest rates", "federal reserve"], ["Wall Street New York", "Federal Reserve Board building"]),
            (["united nations", "un security council", "resolution", "ceasefire", "peacekeeping"], ["United Nations headquarters", "UN Security Council chamber"]),
            (["yemen", "houthi", "red sea", "shipping", "gulf of aden"], ["Yemen Sanaa", "Red Sea shipping"]),
        ]
        for keywords, conc_list in concept_map:
            if any(_match_kw(k, text) for k in keywords):
                for c in conc_list:
                    if c not in concepts:
                        concepts.append(c)

        # -------------------------------------------------------------
        # 2e. Heuristic Named Entity Recognition (Deterministic NLP fallback)
        # -------------------------------------------------------------
        raw_title = event.title or ""
        raw_text = f"{raw_title}. {event.summary or ''}"
        _NER_STOPWORDS = {
            "The", "A", "An", "In", "On", "At", "By", "For", "With", "About", "Against", "Between",
            "Into", "Through", "During", "Before", "After", "Above", "Below", "To", "From", "Up", "Down",
            "News", "Report", "Breaking", "Exclusive", "Update", "Watch", "Live", "Says", "Said", "Says,",
            "Revealed", "Confirmed", "Warns", "Claims", "Urges", "Former", "New", "Latest", "Why", "How",
            "What", "When", "Where", "Who", "Could", "Should", "Would", "May", "Might", "Must", "Will",
            "Can", "Is", "Are", "Was", "Were", "Be", "Been", "Being", "Have", "Has", "Had", "Do", "Does",
            "Did", "But", "And", "Or", "Nor", "So", "Yet", "Both", "Either", "Neither", "Not", "Only",
            "Own", "Same", "Than", "Too", "Very", "Just", "Don't", "Didn't", "Won't", "Can't", "Following",
            "More", "Some", "Many", "Most", "All", "Each", "Every", "Other", "Another", "Such", "French",
            "English", "American", "British", "German", "Spanish", "Italian", "European", "African"
        }

        # Attribution patterns: "says Ryan Giggs", "revealed by Ryan Giggs"
        for m in re.finditer(r"(?:says|said|revealed|claimed|told|according to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", raw_text):
            p = m.group(1).strip()
            if p and p not in _NER_STOPWORDS and not _is_name_subsumed(p, persons):
                persons.append(p)
                if not main_person:
                    main_person = p

        # Action patterns: "scouted Mbappe", "signed Mbappe"
        for m in re.finditer(r"(?:scouted|signed|monitored|targeted|benched|coached|managed|praised|hired|interviewed|defeated|beat)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", raw_text):
            p = m.group(1).strip()
            if p and p not in _NER_STOPWORDS and not _is_name_subsumed(p, persons):
                persons.append(p)
                if not main_person:
                    main_person = p

        # Role patterns: "manager Ryan Giggs", "coach Ryan Giggs"
        for m in re.finditer(r"(?:manager|assistant manager|coach|assistant coach|player|striker|forward|midfielder|defender|goalkeeper|legend|star)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", raw_text):
            p = m.group(1).strip()
            if p and p not in _NER_STOPWORDS and not _is_name_subsumed(p, persons):
                persons.append(p)
                if not main_person:
                    main_person = p

        # Institution patterns: "Manchester United", "Real Madrid", "Arsenal FC"
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:United|City|F\.C\.|FC|Club|Real|Hotspur|Saint-Germain|Munich|Bank|Airlines|Telecom|Corporation|Ministry|Department|Agency|Federation|Association))\b", raw_text):
            inst = clean_entity_name(m.group(1).strip())
            if inst and inst not in _NER_STOPWORDS and not _is_name_subsumed(inst, institutions):
                institutions.append(inst)

        # -------------------------------------------------------------
        # 3. LLM Extraction Enhancement (when available)
        # -------------------------------------------------------------
        if self.text_provider and self.text_provider.is_available():
            try:
                prompt = (
                    "You are a visual photo editor for an international newsdesk.\n"
                    "Analyze this news story and identify the PRIMARY country, key photographic entities, and concrete visual queries.\n"
                    "CRITICAL RULE: If the story is about the United States, Yemen, Kenya, Sudan, Europe, sports, or other international affairs, "
                    "do NOT inject Ethiopian landmarks (e.g. do NOT suggest Addis Ababa, Meskel Square, or Ethiopian institutions unless they are a primary focus).\n\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {(event.summary or '')[:500]}\n"
                    f"Category: {event.primary_category or 'General'}, Region: {event.primary_region or 'International'}\n\n"
                    "Output JSON ONLY:\n"
                    "{\n"
                    '  "country": "Primary country name (e.g. United States, Ethiopia, Kenya, Yemen, United Kingdom, Global)",\n'
                    '  "country_code": "2-letter ISO code (e.g. US, ET, KE, YE, GB, GLOBAL)",\n'
                    '  "topic": "Concise 2-4 word editorial topic",\n'
                    '  "searchable_concepts": ["2-3 word photographic noun query 1", "query 2"],\n'
                    '  "persons": ["Full English name of key figures or officials mentioned"],\n'
                    '  "locations": ["City, capital, or landmark mentioned in story context"],\n'
                    '  "institutions": ["Organization, government department, headquarters, or agency"],\n'
                    '  "suggested_chips": ["Chip 1", "Chip 2", "Chip 3", "Chip 4"]\n'
                    "}"
                )
                req = TextGenerationRequest(prompt=prompt)
                res = self.text_provider.generate_text(req)
                match = re.search(r"\{.*\}", res.text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    llm_c = str(parsed.get("country") or "").strip()
                    llm_cc = str(parsed.get("country_code") or "").strip().upper()
                    if llm_c and llm_c.lower() not in ("null", "none"):
                        country = llm_c
                        if llm_cc and len(llm_cc) >= 2:
                            country_code = llm_cc
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

        # Ensure locations has no empty strings
        locations = [loc for loc in locations if loc and loc.strip()]

        # Defaults if empty
        if not locations:
            if event.primary_region and event.primary_region.lower() not in ("international", "global", "none"):
                locations = [event.primary_region]
            elif default_city:
                locations = [default_city]
            else:
                locations = []

        if not institutions and ctx.get("default_institutions"):
            institutions = list(ctx["default_institutions"][:2])

        if not concepts:
            if ctx.get("default_concepts"):
                concepts = list(ctx["default_concepts"])
            elif persons and institutions:
                is_sports = any(w in text for w in ["football", "soccer", "match", "club", "league", "coach", "scouted"])
                concepts = [f"{persons[0]} {institutions[0]}", f"{institutions[0]} stadium" if is_sports else institutions[0]]
            elif persons:
                concepts = [f"{persons[0]}", f"{persons[0]} portrait"]
            elif institutions:
                concepts = [f"{institutions[0]}", f"{institutions[0]} news"]
            elif locations:
                concepts = [f"{locations[0]} {country}" if country_code not in ("GLOBAL", "ET") else locations[0]]
            else:
                concepts = [event.title[:50]]

        if not topic or topic in ("Ethiopian News", f"{country} News", "Global News", " Global", f" {country}"):
            if persons and institutions:
                topic = f"{persons[0]} & {institutions[0]}"
            elif len(persons) >= 2:
                topic = f"{persons[0]} & {persons[1]}"
            elif persons:
                topic = f"{persons[0]}"
            elif institutions:
                topic = institutions[0]
            elif concepts:
                topic = concepts[0]
            elif locations:
                topic = f"{locations[0]} News"
            else:
                topic = "World News" if country_code == "GLOBAL" else f"{country} News"

        # Build search queries if not already populated from LLM
        if not queries:
            queries = []
            if persons:
                queries.extend(persons[:2])
            if institutions:
                queries.extend(institutions[:2])
            if concepts:
                queries.extend(concepts[:2])
            if locations:
                for loc in locations[:2]:
                    if loc:
                        queries.append(f"{loc} {country}" if country_code not in ("GLOBAL", "ET") else (f"{loc} Ethiopia" if country_code == "ET" else loc))

        # Clean queries (no duplicates, no empty)
        clean_queries = []
        for q in queries:
            q_clean = q.strip()
            if q_clean and q_clean not in clean_queries:
                clean_queries.append(q_clean)
        queries = clean_queries or [event.title[:50]]

        # Build suggested chips
        if not chips:
            chips = []
            if country_code != "GLOBAL" and country and country != "Global":
                chips.append(country)
            for group in (persons, institutions, locations, concepts):
                for item in group:
                    item_clean = item.strip() if item else ""
                    if item_clean and item_clean not in chips and len(item_clean) > 2:
                        chips.append(item_clean)

        entities = StoryVisualEntities(
            topic=topic,
            country=country,
            country_code=country_code,
            default_city=default_city,
            main_person=main_person or (persons[0] if persons else None),
            persons=persons,
            locations=locations,
            institutions=institutions,
            concepts=concepts,
            search_queries=queries,
            suggested_chips=chips[:6],
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
        country_context: str | None = None,
    ) -> list[PhotoCandidate]:
        """Search Wikimedia Commons and Openverse specifically for high-res cityscapes and landmarks."""
        candidates: list[PhotoCandidate] = []
        # 1. First attempt exact Wikipedia lead photo
        wiki_direct = self._resolve_wikipedia_portrait(city_name, entity_type="location", seen_urls=seen_urls)
        if wiki_direct:
            candidates.append(wiki_direct)

        # 2. Wikimedia Commons cityscape search
        ctx = f" {country_context}" if (country_context and country_context.lower() not in ("unknown", "global")) else ""
        queries = [f"{city_name} skyline", f"{city_name}{ctx}".strip(), f"{city_name} landmark"]
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
            ov_res = self._search_openverse_photos(f"{city_name}{ctx}".strip(), seen_urls, limit=4)
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
        country_context: str | None = None,
    ) -> list[PhotoCandidate]:
        """Search Wikipedia and Wikimedia Commons for institution headquarters and facilities."""
        candidates: list[PhotoCandidate] = []
        # 1. Exact Wikipedia lead photo
        wiki_direct = self._resolve_wikipedia_portrait(inst_name, entity_type="institution", seen_urls=seen_urls)
        if wiki_direct:
            candidates.append(wiki_direct)

        # 2. Wikimedia Commons search
        is_sports_club = any(s in inst_name.lower() for s in ["fc", "f.c.", "united", "city", "real", "club", "barcelona", "arsenal", "chelsea", "liverpool", "bayern", "psg", "juventus", "madrid", "milan", "dortmund"])
        search_term = f"{inst_name} stadium" if is_sports_club else f"{inst_name} building"
        c_res = self._search_wikimedia_topic_photos(search_term, seen_urls, limit=4)
        if not c_res and is_sports_club:
            c_res = self._search_wikimedia_topic_photos(inst_name, seen_urls, limit=4)
        for cand in c_res:
            cand.entity_type = "institution"
            cand.entity_name = inst_name
            candidates.append(cand)

        # 3. Openverse search
        if len(candidates) < limit:
            ctx = f" {country_context}" if country_context and country_context.lower() not in ("unknown", "global") else ""
            ov_res = self._search_openverse_photos(f"{inst_name}{ctx}", seen_urls, limit=3)
            for cand in ov_res:
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
