"""Visual intelligence pipeline (Phase 5, spec §§25-32) — Phase 7: dual source."""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ImageGenerationRequest, ImageProvider
from app.models.enums import VisualAssetStatus
from app.models.news_event import NewsEvent
from app.models.social_post import VisualAsset
from app.repositories.visual_asset_repository import VisualAssetRepository
from app.schemas.social_post import PhotoCandidate, PhotoBrowseResponse, SelectCandidateRequest
from app.services.social.editorial_engine import EditorialBrief
from app.services.social.image_critic import ImageCritic
from app.services.social.prompt_engine import PromptEngine
from app.services.social.visual_director import VisualDirector
from app.services.social.web_image_scraper import WebImageScraper

logger = get_logger(__name__)


def extract_article_web_image(url: str) -> str | None:
    """Extract authentic high-resolution editorial photo from an article webpage."""
    if not url or not url.startswith("http"):
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    actual_url = url
    if "news.google.com" in url:
        try:
            from googlenewsdecoder import gnewsdecoder
            decoded = gnewsdecoder(url)
            if decoded.get("status") and decoded.get("decoded_url"):
                actual_url = decoded["decoded_url"]
        except Exception:
            pass

    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
            res = client.get(actual_url)
            if res.status_code == 200:
                text = res.text
                # 1. Open Graph and Twitter image meta tags
                og_patterns = [
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                    r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
                    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
                ]
                for pat in og_patterns:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        img = m.group(1).strip()
                        if img.startswith("//"):
                            img = "https:" + img
                        elif img.startswith("/"):
                            img = urllib.parse.urljoin(str(res.url), img)
                        if img.startswith("http") and not any(img.lower().endswith(ext) for ext in (".svg", ".ico", ".gif")):
                            if "googleusercontent.com" in img:
                                img = re.sub(r"=s\d+.*$", "=s1200", img)
                                if "=s" not in img:
                                    img += "=s1200"
                            return img

                # 2. Prominent article / figure / featured images
                article_patterns = [
                    r'<figure[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']',
                    r'<article[^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']',
                    r'<div[^>]+class=["\'][^"\']*(?:featured|lead|entry-thumb|post-thumb)[^"\']*["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']',
                ]
                for pat in article_patterns:
                    m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
                    if m:
                        img = m.group(1).strip()
                        if img.startswith("//"):
                            img = "https:" + img
                        elif img.startswith("/"):
                            img = urllib.parse.urljoin(str(res.url), img)
                        if img.startswith("http") and not any(img.lower().endswith(ext) for ext in (".svg", ".ico", ".gif")):
                            return img

            # 3. If direct URL failed (e.g. 403 on Cloudflare) but original was Google News:
            if actual_url != url or res.status_code != 200:
                g_res = client.get(url)
                if g_res.status_code == 200:
                    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', g_res.text, re.IGNORECASE)
                    if m:
                        img = m.group(1).strip()
                        if "googleusercontent.com" in img:
                            img = re.sub(r"=s\d+.*$", "=s1200", img)
                            if "=s" not in img:
                                img += "=s1200"
                        return img
    except Exception:
        pass

    return None



@dataclass
class ImagePipelineResult:
    selected_asset: VisualAsset
    all_assets: list[VisualAsset]
    attempts: int
    error: str | None = None


class ImagePipeline:
    def __init__(
        self,
        session: Session,
        text_provider: AIProvider,
        image_provider: ImageProvider,
    ) -> None:
        self.session = session
        self.director = VisualDirector(text_provider)
        self.prompt_engine = PromptEngine()
        self.critic = ImageCritic(text_provider)
        self.asset_repo = VisualAssetRepository(session)
        self.image_provider = image_provider

    # ------------------------------------------------------------------
    # Public entry: AI generation
    # ------------------------------------------------------------------
    def run(self, event: NewsEvent, brief: EditorialBrief) -> ImagePipelineResult:
        """Generate AI image (FLUX via Pollinations). Story-context-aware prompt."""
        strategy = self.director.direct(event, brief.headline, brief.short_summary)
        ctx = strategy.story_context
        prompt = self.prompt_engine.build_prompt(strategy, event, ctx)

        logger.info(
            "image_pipeline_prompt",
            event_id=str(event.id),
            prompt_preview=prompt[:120],
        )

        all_assets: list[VisualAsset] = []
        best_asset = None
        best_score = -1

        for attempt in range(settings.max_image_retries + 1):
            req = ImageGenerationRequest(prompt=prompt)
            res = self.image_provider.generate_image(req)

            report = self.critic.evaluate(res.image_bytes or b"", strategy, event.title)

            asset = VisualAsset(
                event_id=event.id,
                prompt=prompt,
                visual_strategy={"strategy": strategy.visual_strategy, "style": strategy.style},
                provider=self.image_provider.name,
                model=res.model,
                style=strategy.style,
                quality_score=report.overall_score,
                quality_report={
                    "issues": report.issues,
                    "recommendation": report.recommendation,
                    "image_source": "ai_generated",
                    "prompt_preview": prompt[:200],
                },
                status=(
                    VisualAssetStatus.generated
                    if report.recommendation == "approve"
                    else VisualAssetStatus.rejected
                ),
                is_selected=False,
            )
            self.asset_repo.create(asset)
            asset = self._persist_image(asset, res.image_bytes, res.image_url)

            all_assets.append(asset)

            if report.overall_score > best_score:
                best_score = report.overall_score
                best_asset = asset

            if (
                report.recommendation == "approve"
                and report.overall_score >= settings.image_quality_threshold
            ):
                break

        if best_asset:
            self.asset_repo.mark_selected(best_asset.id)

        return ImagePipelineResult(
            selected_asset=best_asset,
            all_assets=all_assets,
            attempts=len(all_assets),
        )

    # ------------------------------------------------------------------
    # Public entry: real article photo
    # ------------------------------------------------------------------
    def run_real_photo(self, event: NewsEvent) -> ImagePipelineResult:
        """Fetch the authentic article photo from the source publisher as the visual asset."""
        image_url, source_name = self._find_article_image_url(event)
        image_bytes = self._download_image(image_url) if image_url else None

        # If article photo not available or download failed, search authentic editorial photos
        if not image_bytes or not image_url:
            logger.info("article_photo_unavailable_trying_wikimedia", event_id=str(event.id))
            browse_res = self.browse_photos(event)
            if browse_res.items:
                c0 = browse_res.items[0]
                req = SelectCandidateRequest(
                    event_id=event.id,
                    image_url=c0.image_url,
                    title=c0.title,
                    photographer=c0.photographer,
                    source=c0.source,
                )
                asset = self.import_candidate(event, req)
                return ImagePipelineResult(
                    selected_asset=asset,
                    all_assets=[asset],
                    attempts=1,
                )

            # If even browsing has no match, fall back to contextual AI generation
            logger.info("fallback_to_ai_generation", event_id=str(event.id))
            from app.services.social.editorial_engine import EditorialEngine
            editorial = EditorialEngine(self.director.provider)
            brief = editorial.compose(event)
            return self.run(event, brief)

        # Save authentic source photo as a VisualAsset
        src_label = source_name or "News Source"
        asset = VisualAsset(
            event_id=event.id,
            prompt=f"Authentic article photo from {src_label}: {image_url}",
            visual_strategy={"strategy": "real_article_photo", "source": src_label},
            provider="article_source",
            model=src_label,
            style="News Article Photo",
            quality_score=95,
            quality_report={
                "image_source": "article_source",
                "publisher": src_label,
                "source_url": image_url,
                "issues": [],
                "recommendation": "approve",
            },
            status=VisualAssetStatus.approved,
            is_selected=True,
        )
        self.asset_repo.create(asset)
        asset = self._persist_image(asset, image_bytes, None)
        self.asset_repo.mark_selected(asset.id)
        self.session.flush()

        logger.info("article_source_photo_saved", event_id=str(event.id), asset_id=str(asset.id), source=src_label)
        return ImagePipelineResult(
            selected_asset=asset,
            all_assets=[asset],
            attempts=1,
        )

    # ------------------------------------------------------------------
    # Public entry: Topic-based Internet Photo Browsing with Pagination
    # ------------------------------------------------------------------
    def browse_photos(
        self,
        event: NewsEvent,
        query: str | None = None,
        page: int = 1,
        page_size: int = 6,
    ) -> PhotoBrowseResponse:
        """Search the internet for real photo alternatives based on the news topic.

        Features:
        - Expanded multi-source search (all article photos + Wikipedia + Wikimedia Commons + Pexels).
        - Multi-facet queries ensuring genuine topic relevance (no unrelated homonyms or food dishes).
        - Excludes maps, plans, diagrams, flags, seals, and non-photo graphics.
        - In-memory pooling & caching for instant pagination (Next 6 / Previous).
        - Does NOT save or persist unselected assets to the database or filesystem.
        """
        import time

        global _PHOTO_POOL_CACHE
        if "_PHOTO_POOL_CACHE" not in globals():
            _PHOTO_POOL_CACHE = {}

        cache_key = f"{event.id}:{query.strip().lower() if query else ''}"
        now = time.time()

        if cache_key in _PHOTO_POOL_CACHE:
            cached_entry = _PHOTO_POOL_CACHE[cache_key]
            cached_time = cached_entry[0]
            if now - cached_time < 300.0:  # 5 minute TTL
                cached_pool = cached_entry[1]
                cached_topic = cached_entry[2]
                cached_person = cached_entry[3] if len(cached_entry) > 3 else None
                cached_queries = cached_entry[4] if len(cached_entry) > 4 else []
                cached_chips = cached_entry[5] if len(cached_entry) > 5 else []
                return self._paginate_pool(
                    cached_pool,
                    cached_topic,
                    page,
                    page_size,
                    detected_person=cached_person,
                    search_queries=cached_queries,
                    suggested_chips=cached_chips,
                )

        # 1. AI Story Understanding: extract topic, central person, search queries, and suggested chips
        from app.services.social.web_image_scraper import WebImageScraper
        scraper = WebImageScraper(self.director.provider)
        topic, detected_person, search_queries, suggested_chips = scraper.analyze_story(event, custom_query=query)

        # 2. Gather candidates from all available sources
        pool = self._gather_candidate_pool(
            event,
            topic=topic,
            facets=search_queries,
            keywords=set(),
            max_pool=30,
            user_query=query,
            scraper=scraper,
        )

        # 3. Store in cache
        _PHOTO_POOL_CACHE[cache_key] = (now, pool, topic, detected_person, search_queries, suggested_chips)

        return self._paginate_pool(
            pool,
            topic,
            page,
            page_size,
            detected_person=detected_person,
            search_queries=search_queries,
            suggested_chips=suggested_chips,
        )

    def _paginate_pool(
        self,
        pool: list[PhotoCandidate],
        topic: str,
        page: int,
        page_size: int,
        detected_person: str | None = None,
        search_queries: list[str] | None = None,
        suggested_chips: list[str] | None = None,
    ) -> PhotoBrowseResponse:
        """Slice candidate pool into 6-item pages."""
        total_items = len(pool)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        current_page = min(max(1, page), total_pages)
        start = (current_page - 1) * page_size
        items = pool[start:start + page_size]

        return PhotoBrowseResponse(
            items=items,
            page=current_page,
            total_pages=total_pages,
            total_items=total_items,
            has_next=current_page < total_pages,
            has_prev=current_page > 1,
            topic=topic,
            detected_person=detected_person,
            search_queries=search_queries or [],
            suggested_chips=suggested_chips or [],
        )

    def import_candidate(self, event: NewsEvent, req: SelectCandidateRequest) -> VisualAsset:
        """Download ONLY the single candidate chosen by the user and import into Photo Studio."""
        img_bytes = self._download_image(req.image_url)
        asset = VisualAsset(
            event_id=event.id,
            prompt=f"Selected {req.source} photo: {req.title}",
            visual_strategy={"strategy": f"{req.source}_selected", "title": req.title},
            provider=req.source,
            model=f"{req.source}/{req.photographer}",
            style="Real Editorial Photo",
            quality_score=90,
            quality_report={
                "image_source": req.source,
                "title": req.title,
                "photographer": req.photographer,
                "source_url": req.image_url,
                "issues": [],
                "recommendation": "approve",
            },
            status=VisualAssetStatus.generated,
            is_selected=True,
        )
        self.asset_repo.create(asset)
        asset = self._persist_image(asset, img_bytes, req.image_url)
        self.asset_repo.mark_selected(asset.id)
        self.session.commit()
        self.session.refresh(asset)
        logger.info("imported_visual_candidate", asset_id=str(asset.id), event_id=str(event.id), source=req.source)
        return asset

    def _extract_topic_facets(
        self, event: NewsEvent, custom_query: str | None = None
    ) -> tuple[str, list[str], set[str]]:
        """Extract multi-facet search queries and strict topic keywords for accurate matching."""
        import re

        if custom_query and custom_query.strip():
            q = custom_query.strip()
            topic = q
            facets = [
                q,
                f"{q} Ethiopia" if "ethiopia" not in q.lower() else q,
                f"Contemporary {q}",
            ]
            keywords = {w.lower() for w in re.split(r"\W+", q) if len(w) > 2} | {"ethiopia"}
            return topic, facets, keywords

        text = f"{event.title or ''} {event.summary or ''} {event.primary_category or ''} {event.primary_region or ''}".lower()

        # 0. Prime Minister / Abiy Ahmed / Leadership / Politics / Government
        if any(k in text for k in ["ዐቢይ", "አብይ", "ጠቅላይ ሚኒስትር", "መንግስት", "ፓርላማ", "ፕሬዝዳንት", "abiy", "prime minister", "president", "parliament"]):
            topic = "Prime Minister Abiy Ahmed & Ethiopian Leadership"
            facets = [
                "Abiy Ahmed",
                "Prime Minister of Ethiopia",
                "Premiership of Abiy Ahmed",
                "Council of Ministers of Abiy Ahmed",
                "Government of Ethiopia",
            ]
            keywords = {
                "abiy", "ahmed", "minister", "prime", "ethiopia", "president",
                "government", "official", "parliament", "premiership", "leader", "speech"
            }
            return topic, facets, keywords

        # 1. Mojo / Modjo / Logistics / Port / Railway
        if any(k in text for k in ["ሞጆ", "modjo", "mojo", "ሎጂስቲክስ", "ደረቅ ወደብ", "port", "logistics"]):
            topic = "Mojo Logistics & Dry Port"
            facets = [
                "Mojo dry port Ethiopia",
                "Ethiopian Railway Corporation freight",
                "Addis Ababa Djibouti railway",
                "Transport in Ethiopia logistics",
                "Modjo Oromia Ethiopia",
            ]
            keywords = {
                "mojo", "modjo", "port", "railway", "freight", "transport", "cargo",
                "djibouti", "ethiopia", "oromia", "adama", "train", "logistics", "shipping"
            }
            return topic, facets, keywords

        # 2. Fire / Emergency / Disaster / Rescue
        if any(k in text for k in ["እሳት", "አደጋ", "fire", "emergency", "disaster", "rescue"]):
            topic = "Fire & Emergency Services"
            facets = [
                "Firefighting in Ethiopia",
                "Addis Ababa Fire and Emergency",
                "Emergency services in Ethiopia",
                "Addis Ababa emergency",
                "Disaster management Ethiopia",
            ]
            keywords = {
                "fire", "emergency", "rescue", "firefighter", "disaster", "addis",
                "ethiopia", "hazard", "safety", "commission", "truck"
            }
            return topic, facets, keywords

        # 3. Inflation / Economy / Bank / Birr / Finance
        if any(k in text for k in ["ዋጋ ግሽበት", "inflation", "ምንዛሪ", "exchange rate", "ብር", "ባንክ", "ንግድ ባንክ", "ኢኮኖሚ", "economy", "bank"]):
            topic = "Ethiopian Economy & Banking"
            facets = [
                "Commercial Bank of Ethiopia",
                "National Bank of Ethiopia",
                "Economy of Ethiopia",
                "Ethiopian birr",
                "Banking in Ethiopia",
                "Addis Ababa financial district",
            ]
            keywords = {
                "bank", "economy", "birr", "currency", "finance", "commercial",
                "economic", "trade", "market", "central", "banking", "financial"
            }
            return topic, facets, keywords

        # 4. GERD / Blue Nile / Abbay Dam
        if any(k in text for k in ["ህዳሴ", "ግድብ", "ዓባይ", "abbay", "gerd", "nile", "dam"]):
            topic = "Grand Ethiopian Renaissance Dam"
            facets = [
                "Grand Ethiopian Renaissance Dam",
                "Blue Nile Falls Ethiopia",
                "Abbay River Ethiopia",
                "Benishangul-Gumuz Region",
                "Hydroelectric power in Ethiopia",
            ]
            keywords = {
                "dam", "nile", "gerd", "renaissance", "abbay", "water", "reservoir",
                "ethiopia", "hydroelectric", "blue nile", "river"
            }
            return topic, facets, keywords

        # 5. Ethiopian Airlines / Aviation / Airport
        if any(k in text for k in ["አየር መንገድ", "airline", "airlines", "flight", "airport", "ቦሌ"]):
            topic = "Ethiopian Airlines & Aviation"
            facets = [
                "Ethiopian Airlines",
                "Addis Ababa Bole International Airport",
                "Ethiopian Airlines fleet",
                "Aviation in Ethiopia",
            ]
            keywords = {
                "airline", "airlines", "airplane", "aircraft", "airport", "bole",
                "ethiopian", "aviation", "flight", "runway"
            }
            return topic, facets, keywords

        # 6. Ethio Telecom / Technology
        if any(k in text for k in ["ቴሌ", "ቴሌኮም", "telecom", "telecommunications"]):
            topic = "Ethio Telecom & Technology"
            facets = [
                "Ethio telecom",
                "Telecommunications in Ethiopia",
                "Safaricom Telecommunications Ethiopia",
                "Technology in Ethiopia",
            ]
            keywords = {
                "telecom", "telecommunications", "mobile", "phone", "network",
                "ethiopia", "internet", "technology"
            }
            return topic, facets, keywords

        # 7. Regional News / Specific Regional Capitals
        region_topics = {
            "tigray": ("Tigray Region", ["Tigray Ethiopia", "Mekelle city Ethiopia", "Tigray highlands"]),
            "amhara": ("Amhara Region", ["Amhara Ethiopia", "Gondar Ethiopia", "Bahir Dar Lake Tana"]),
            "oromia": ("Oromia Region", ["Oromia Ethiopia", "Adama city Ethiopia", "Bishoftu Ethiopia"]),
            "somali": ("Somali Region", ["Somali Region Ethiopia", "Jijiga Ethiopia", "Ogaden Ethiopia"]),
            "afar": ("Afar Region", ["Afar Region Ethiopia", "Semera Ethiopia", "Danakil Ethiopia"]),
            "sidama": ("Sidama Region", ["Sidama Region Ethiopia", "Hawassa Lake Hawassa", "Hawassa Ethiopia"]),
            "dire dawa": ("Dire Dawa", ["Dire Dawa Ethiopia", "Dire Dawa city", "Eastern Ethiopia"]),
        }
        for rk, (rtopic, rfacets) in region_topics.items():
            if rk in text:
                keywords = {rk, "ethiopia", "city", "region", "capital", "contemporary"}
                return rtopic, rfacets, keywords

        # Default: clean English words from title or region
        clean_words = [w for w in re.split(r"\W+", event.title or "") if len(w) > 3 and not re.search(r"[\u1200-\u137F]", w)]
        subj = " ".join(clean_words[:3]) if clean_words else (event.primary_region or "Addis Ababa")
        topic = f"{subj} Ethiopia"
        facets = [
            f"{subj} Ethiopia",
            f"{event.primary_region} Ethiopia" if event.primary_region else "Addis Ababa Ethiopia",
            "Contemporary Ethiopia",
        ]
        keywords = {"ethiopia", "addis", "ababa", (event.primary_region or "").lower()}
        return topic, facets, keywords

    def _gather_candidate_pool(
        self,
        event: NewsEvent,
        topic: str,
        facets: list[str],
        keywords: set[str],
        max_pool: int = 30,
        user_query: str | None = None,
        scraper: Any = None,
    ) -> list[PhotoCandidate]:
        """Aggregate photos from all available sources with strict topic filtering."""
        import urllib.parse
        seen_urls: set[str] = set()
        pool: list[PhotoCandidate] = []

        # --- Source 1: Live Web Image Scraper (Direct Article Media + Person Search + Live Web Photos + Firecrawl) ---
        try:
            if scraper is None:
                from app.services.social.web_image_scraper import WebImageScraper
                scraper = WebImageScraper(self.director.provider)
            live_candidates = scraper.search_candidates(event, custom_query=user_query, max_pool=max_pool)
            for cand in live_candidates:
                if cand.image_url not in seen_urls:
                    seen_urls.add(cand.image_url)
                    pool.append(cand)
        except Exception as exc:
            logger.warning("live_web_image_scraper_failed", error=str(exc))

        # Fast exit: if live web scraper already gathered >= 12 authentic candidates (2 full pages), return immediately
        if len(pool) >= 12:
            return pool

        # Exclusion list: no SVGs, PDFs, maps, diagrams, coats of arms, flags, or logos
        non_photo_patterns = (
            ".svg", ".gif", ".pdf",
            "map of", "map ", "map_", "/map", "karte", "carte", "plan ", "diagram", "chart",
            "coat of arms", "emblem", "flag of", "flag_", "/flag", "logo", "insignia", "seal of"
        )

        is_conflict_topic = any(k in topic.lower() for k in ["war", "conflict", "battle", "military", "army"])
        generic_negative_terms = (" war", "battle of", "massacre", "famine in", "corpse", "casualty")

        # --- Source 2: Backfill from Linked Article Photos (if not already captured) ---
        article_images = self._find_all_article_images(event)
        for url, art_title, source_label, photographer in article_images:
            if len(pool) >= 18:
                break
            if url not in seen_urls:
                seen_urls.add(url)
                pool.append(
                    PhotoCandidate(
                        id=f"article-{len(pool)}",
                        title=art_title[:80],
                        thumb_url=url,
                        image_url=url,
                        source=source_label,
                        photographer=photographer,
                        description="Original photo published with this news article",
                    )
                )

        if len(pool) >= 12:
            return pool

        # --- Source 3: Backfill from Wikipedia Article Page Images if pool has room ---
        headers = {
            "User-Agent": "ETHIOTIMESBot/1.0 (editorial-studio@ethiotimes.org; contact: info@ethiotimes.com)"
        }

        for q in facets[:2]:
            if len(pool) >= 12:
                break
            w_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&generator=search"
                f"&gsrsearch={urllib.parse.quote(q)}"
                f"&gsrlimit=6&prop=pageimages|extracts&pithumbsize=1000&exintro=1&explaintext=1&exsentences=2&format=json"
            )
            try:
                with httpx.Client(timeout=3.0) as client:
                    res = client.get(w_url, headers=headers)
                    if res.status_code == 200:
                        pages = res.json().get("query", {}).get("pages", {})
                        for pid, p in pages.items():
                            thumb = p.get("thumbnail", {}).get("source")
                            if not thumb or thumb in seen_urls:
                                continue
                            if any(x in thumb.lower() for x in non_photo_patterns):
                                continue

                            title_item = p.get("title", "")
                            if any(x in title_item.lower() for x in non_photo_patterns):
                                continue
                            if not is_conflict_topic and any(term in title_item.lower() for term in generic_negative_terms):
                                continue

                            extract = p.get("extract", "")
                            combined = f"{title_item} {extract}".lower()

                            # Strict relevance filter: must match at least one topic keyword
                            if not any(kw in combined for kw in keywords):
                                continue

                            seen_urls.add(thumb)
                            pool.append(
                                PhotoCandidate(
                                    id=f"wiki-{pid}",
                                    title=title_item,
                                    thumb_url=thumb,
                                    image_url=thumb,
                                    source="wikimedia",
                                    photographer="Wikipedia Editorial",
                                    description=extract[:120] if extract else None,
                                )
                            )
            except Exception as exc:
                logger.warning("wiki_facet_search_failed", query=q, error=str(exc))

        if len(pool) >= 12:
            return pool

        # --- Source 4: Wikimedia Commons Direct Bitmap Archive ---
        for q in facets[:2]:
            if len(pool) >= 12:
                break
            c_url = (
                f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
                f"&gsrsearch={urllib.parse.quote(q + ' filetype:bitmap')}"
                f"&gsrnamespace=6&gsrlimit=6&prop=imageinfo&iiprop=url&iiurlwidth=1000&format=json"
            )
            try:
                with httpx.Client(timeout=3.0) as client:
                    res = client.get(c_url, headers=headers)
                    if res.status_code == 200:
                        pages = res.json().get("query", {}).get("pages", {})
                        for pid, p in pages.items():
                            ii = p.get("imageinfo", [{}])[0]
                            thumb = ii.get("thumburl") or ii.get("url")
                            if not thumb or thumb in seen_urls:
                                continue
                            if any(x in thumb.lower() for x in non_photo_patterns):
                                continue

                            title_clean = p.get("title", "").replace("File:", "").replace("_", " ")
                            title_lower = title_clean.lower()
                            if any(x in title_lower for x in non_photo_patterns):
                                continue
                            if not is_conflict_topic and any(term in title_lower for term in generic_negative_terms):
                                continue
                            if keywords and not any(kw in title_lower for kw in keywords):
                                continue

                            seen_urls.add(thumb)
                            pool.append(
                                PhotoCandidate(
                                    id=f"commons-{pid}",
                                    title=title_clean[:70],
                                    thumb_url=thumb,
                                    image_url=ii.get("url") or thumb,
                                    source="wikimedia",
                                    photographer="Wikimedia Commons",
                                    description=f"Wikimedia Archive: {title_clean[:70]}",
                                )
                            )
            except Exception as exc:
                logger.warning("commons_facet_search_failed", query=q, error=str(exc))

        # --- Source 4: Pexels API (if configured) ---
        pexels_key = getattr(settings, "pexels_api_key", None)
        if pexels_key and len(pool) < max_pool:
            pexels_candidates = self._fetch_pexels_candidates(topic, pexels_key, seen_urls)
            pool.extend(pexels_candidates)

        return pool

    def _fetch_pexels_candidates(
        self, topic: str, api_key: str, seen_urls: set[str], limit: int = 6
    ) -> list[PhotoCandidate]:
        """Fetch photos from Pexels API when key is configured."""
        import urllib.parse
        if not api_key:
            return []
        candidates: list[PhotoCandidate] = []
        try:
            url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(topic)}&per_page={limit}"
            headers = {"Authorization": api_key}
            with httpx.Client(timeout=6.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    for p in data.get("photos", []):
                        src = p.get("src", {})
                        img_url = src.get("large2x") or src.get("large") or src.get("original")
                        thumb_url = src.get("medium") or src.get("small") or img_url
                        if img_url and img_url not in seen_urls:
                            seen_urls.add(img_url)
                            candidates.append(
                                PhotoCandidate(
                                    id=f"pexels-{p.get('id')}",
                                    title=p.get("alt") or f"Pexels: {topic}",
                                    thumb_url=thumb_url,
                                    image_url=img_url,
                                    source="pexels",
                                    photographer=p.get("photographer") or "Pexels",
                                    description=f"Pexels photo by {p.get('photographer')}",
                                )
                            )
        except Exception as exc:
            logger.warning("pexels_fetch_failed", error=str(exc))
        return candidates

    def _find_all_article_images(self, event: NewsEvent) -> list[tuple[str, str, str, str]]:
        """Return list of (image_url, title, source_label, photographer) from all linked articles."""
        from app.models.article import Article
        from app.models.news_event import EventArticle
        results = []
        seen = set()
        try:
            # 1. From event.article_links relationship
            if hasattr(event, "article_links") and event.article_links:
                for link in event.article_links:
                    art = getattr(link, "article", None)
                    if art and art.image_url and art.image_url.strip().startswith("http"):
                        url = art.image_url.strip()
                        if url not in seen:
                            seen.add(url)
                            is_tg = "t.me" in url or "telegram" in url.lower() or (art.source and "telegram" in (art.source.name or "").lower())
                            source_label = "telegram" if is_tg else "article"
                            photographer = "Telegram Channel" if is_tg else (art.source.name if art.source else "Article Source")
                            results.append((url, art.title or event.title, source_label, photographer))

            # 2. From direct query
            articles = (
                self.session.query(Article)
                .join(EventArticle, EventArticle.article_id == Article.id)
                .filter(EventArticle.event_id == event.id)
                .all()
            )
            for art in articles:
                if art.image_url and art.image_url.strip().startswith("http"):
                    url = art.image_url.strip()
                    if url not in seen:
                        seen.add(url)
                        is_tg = "t.me" in url or "telegram" in url.lower() or (art.source and "telegram" in (art.source.name or "").lower())
                        source_label = "telegram" if is_tg else "article"
                        photographer = "Telegram Channel" if is_tg else (art.source.name if art.source else "Article Source")
                        results.append((url, art.title or event.title, source_label, photographer))
        except Exception as exc:
            logger.warning("find_all_article_images_failed", error=str(exc))
        return results

    # Legacy support
    def search_pexels(self, event: NewsEvent, query: str | None = None) -> list[VisualAsset]:
        browse_res = self.browse_photos(event, query=query)
        assets = []
        for c in browse_res.items:
            req = SelectCandidateRequest(
                event_id=event.id,
                image_url=c.image_url,
                title=c.title,
                photographer=c.photographer,
                source=c.source,
            )
            assets.append(self.import_candidate(event, req))
        return assets

    def search_wikimedia(self, event: NewsEvent, query: str | None = None) -> list[VisualAsset]:
        return self.search_pexels(event, query=query)


    # Legacy support
    def search_pexels(self, event: NewsEvent, query: str | None = None) -> list[VisualAsset]:
        candidates = self.browse_photos(event, query=query)
        assets = []
        for c in candidates:
            req = SelectCandidateRequest(
                event_id=event.id,
                image_url=c.image_url,
                title=c.title,
                photographer=c.photographer,
                source=c.source,
            )
            assets.append(self.import_candidate(event, req))
        return assets

    def search_wikimedia(self, event: NewsEvent, query: str | None = None) -> list[VisualAsset]:
        return self.search_pexels(event, query=query)


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_article_image_url(self, event: NewsEvent) -> tuple[str | None, str | None]:
        """Find authentic editorial photo URL from the event's linked articles.
        
        Returns (image_url, source_name).
        Persists newly discovered image_url back to Article row for future use.
        """
        from app.models.article import Article
        from app.models.news_event import EventArticle

        articles: list[Article] = []
        try:
            # 1. Check in-memory relationships if loaded
            if hasattr(event, "article_links") and event.article_links:
                for link in event.article_links:
                    art = getattr(link, "article", None)
                    if art:
                        articles.append(art)

            # 2. Query EventArticle -> Article if not loaded
            if not articles:
                articles = (
                    self.session.query(Article)
                    .join(EventArticle, EventArticle.article_id == Article.id)
                    .filter(EventArticle.event_id == event.id)
                    .all()
                )
        except Exception as exc:
            logger.warning("collect_event_articles_failed", error=str(exc))

        # 3. Check if any linked article already has a valid image_url
        for art in articles:
            if art.image_url and art.image_url.strip().startswith("http"):
                src_name = getattr(art.source, "name", "News Source") if hasattr(art, "source") and art.source else "News Source"
                return art.image_url.strip(), src_name

        # 4. Live extraction from article web pages (Open Graph / article lead photo)
        for art in articles:
            target_url = art.url or art.canonical_url
            if not target_url:
                continue
            extracted = extract_article_web_image(target_url)
            if extracted:
                try:
                    art.image_url = extracted
                    self.session.flush()
                except Exception:
                    pass
                src_name = getattr(art.source, "name", "News Source") if hasattr(art, "source") and art.source else "News Source"
                logger.info("extracted_article_image", event_id=str(event.id), source=src_name, image_url=extracted[:80])
                return extracted, src_name

        return None, None

    def _download_image(self, url: str) -> bytes | None:
        """Download an image with browser headers and return bytes if valid (>3KB)."""
        if not url:
            return None
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
                res = client.get(url)
                if res.status_code == 200 and len(res.content) > 3000:
                    return res.content
        except Exception as exc:
            logger.warning("image_download_failed", url=url, error=str(exc))
        return None

    def _persist_image(
        self, asset: VisualAsset, image_bytes: bytes | None, image_url: str | None
    ) -> VisualAsset:
        """Write image bytes to disk and set storage fields."""
        media_dir = Path(settings.media_root) / "assets"
        media_dir.mkdir(parents=True, exist_ok=True)
        storage_path = media_dir / f"{asset.id}.png"
        if image_bytes:
            storage_path.write_bytes(image_bytes)
            asset.storage_path = str(storage_path)
            asset.storage_url = f"/api/v1/posts/assets/{asset.id}/image"
        elif image_url:
            asset.storage_url = image_url
        self.session.flush()
        return asset

    def _build_pexels_query(self, event: NewsEvent) -> str:
        """Build a contextual Pexels search query from event data."""
        parts = []
        if event.primary_region:
            parts.append(event.primary_region)
        elif event.primary_category:
            parts.append(event.primary_category)
        parts.append("Ethiopia")
        title_words = (event.title or "").split()[:4]
        parts.extend(title_words)
        return " ".join(parts[:8])
