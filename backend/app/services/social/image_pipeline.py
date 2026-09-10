"""Visual intelligence pipeline (Phase 5, spec §§25-32) — Phase 7: dual source."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ImageGenerationRequest, ImageProvider
from app.models.enums import VisualAssetStatus
from app.models.news_event import NewsEvent
from app.models.social_post import VisualAsset
from app.repositories.visual_asset_repository import VisualAssetRepository
from app.schemas.social_post import PhotoCandidate, SelectCandidateRequest
from app.services.social.editorial_engine import EditorialBrief
from app.services.social.image_critic import ImageCritic
from app.services.social.prompt_engine import PromptEngine
from app.services.social.visual_director import VisualDirector

logger = get_logger(__name__)


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
        """Try to fetch a real photo from the event's linked articles, or Wikimedia."""
        image_url = self._find_article_image_url(event)
        image_bytes = self._download_image(image_url) if image_url else None

        # If article photo not available or download failed, search Wikipedia for a real photo
        if not image_bytes:
            logger.info("article_photo_unavailable_trying_wikimedia", event_id=str(event.id))
            candidates = self.browse_photos(event)
            if candidates:
                c0 = candidates[0]
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

            # If even Wikimedia has no match, fall back to contextual AI generation
            logger.info("fallback_to_ai_generation", event_id=str(event.id))
            from app.services.social.editorial_engine import EditorialEngine
            editorial = EditorialEngine(self.director.provider)
            brief = editorial.compose(event)
            return self.run(event, brief)

        # Save as a real_photo VisualAsset
        strategy = self.director.direct(event, event.title, event.summary or "")
        asset = VisualAsset(
            event_id=event.id,
            prompt=f"Real article photo from: {image_url}",
            visual_strategy={"strategy": "real_photo"},
            provider="real_photo",
            model="article_source",
            style="Real News Photo",
            quality_score=85,
            quality_report={
                "image_source": "real_photo",
                "source_url": image_url,
                "issues": [],
                "recommendation": "approve",
            },
            status=VisualAssetStatus.generated,
            is_selected=False,
        )
        self.asset_repo.create(asset)
        asset = self._persist_image(asset, image_bytes, None)
        self.asset_repo.mark_selected(asset.id)

        return ImagePipelineResult(
            selected_asset=asset,
            all_assets=[asset],
            attempts=1,
        )

    # ------------------------------------------------------------------
    # Public entry: Topic-based Internet Photo Browsing (6 Alternatives)
    # ------------------------------------------------------------------
    def browse_photos(self, event: NewsEvent, query: str | None = None) -> list[PhotoCandidate]:
        """Search the internet for real photo alternatives based on the news topic.

        Returns exactly up to 6 alternatives.
        Candidate 1 is the real article photo if available.
        Remaining candidates are high-res editorial photos from Wikimedia / Pexels.
        DOES NOT save or persist to the database or filesystem.
        """
        topic = self._resolve_topic_query(event, query)
        candidates: list[PhotoCandidate] = []
        seen_urls: set[str] = set()

        # 1. Candidate #1: Real article photo if linked
        article_url = self._find_article_image_url(event)
        if article_url and article_url.startswith("http"):
            is_telegram = "t.me" in article_url or "telegram" in article_url.lower()
            source_label = "telegram" if is_telegram else "article"
            photographer = "Telegram Source" if is_telegram else "Article Source"
            candidates.append(
                PhotoCandidate(
                    id="article-source-photo",
                    title=event.title[:80],
                    thumb_url=article_url,
                    image_url=article_url,
                    source=source_label,
                    photographer=photographer,
                    description="Original photo published with this news article",
                )
            )
            seen_urls.add(article_url)

        # 2. Query Wikimedia Commons / Wikipedia for topic photos
        wiki_candidates = self._fetch_wiki_candidates(topic, seen_urls)
        candidates.extend(wiki_candidates)

        # 3. If fewer than 6, query a secondary fallback topic to reach 6
        if len(candidates) < 6:
            fallback_topic = (
                f"{event.primary_region} Ethiopia"
                if event.primary_region and event.primary_region.lower() not in topic.lower()
                else "Addis Ababa Ethiopia"
            )
            if fallback_topic != topic:
                extra_wiki = self._fetch_wiki_candidates(fallback_topic, seen_urls)
                candidates.extend(extra_wiki)

        # 4. If Pexels is configured, also fetch Pexels candidates
        pexels_key = getattr(settings, "pexels_api_key", None)
        if pexels_key and len(candidates) < 6:
            pexels_candidates = self._fetch_pexels_candidates(topic, pexels_key, seen_urls)
            candidates.extend(pexels_candidates)

        return candidates[:6]

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

    def _resolve_topic_query(self, event: NewsEvent, custom_query: str | None = None) -> str:
        """Resolve a concise 2-4 word English topic search query for Wikipedia / Pexels."""
        if custom_query and custom_query.strip():
            q = custom_query.strip()
            if "ethiopia" not in q.lower():
                return f"{q} Ethiopia"
            return q

        # 1. Try AgentRouter text provider if available
        if self.director.provider and self.director.provider.is_available():
            try:
                from app.integrations.ai.base import TextGenerationRequest
                prompt = (
                    f"Given this Ethiopian news story:\n"
                    f"Headline: {event.title}\n"
                    f"Summary: {event.summary or ''}\n\n"
                    "Extract a 2 to 4 word English search topic to find relevant editorial photos on Wikipedia (e.g. 'Mojo dry port Ethiopia', 'GERD dam Ethiopia', 'Addis Ababa light rail', 'Ethiopia coffee harvest').\n"
                    "Output ONLY the search keywords without quotes or punctuation."
                )
                res = self.director.provider.generate_text(
                    TextGenerationRequest(prompt=prompt, max_tokens=1024, temperature=0.1)
                )
                topic = res.text.strip().replace('"', '').replace("'", "")
                topic = topic.split("\n")[0].strip()
                if len(topic) >= 3 and len(topic) <= 60:
                    if "ethiopia" not in topic.lower():
                        topic = f"{topic} Ethiopia"
                    logger.info("resolved_topic_query_llm", topic=topic, event_id=str(event.id))
                    return topic
            except Exception as exc:
                logger.warning("resolve_topic_llm_failed_fallback", error=str(exc))

        # 2. Heuristic fallback based on keywords & entities
        text = f"{event.title or ''} {event.summary or ''}".lower()
        if any(k in text for k in ["ሞጆ", "modjo", "mojo", "ሎጂስቲክስ", "ደረቅ ወደብ"]):
            return "Mojo dry port Ethiopia"
        if any(k in text for k in ["ህዳሴ", "ግድብ", "ዓባይ", "abbay", "gerd", "nile"]):
            return "Grand Ethiopian Renaissance Dam Ethiopia"
        if any(k in text for k in ["ቴሌ", "ቴሌኮም", "telecom"]):
            return "Ethio telecom Ethiopia"
        if any(k in text for k in ["አየር መንገድ", "airlines", "flight"]):
            return "Ethiopian Airlines"
        if any(k in text for k in ["ዋጋ ግሽበት", "inflation", "ምንዛሪ", "exchange rate", "ብር"]):
            return "Commercial Bank of Ethiopia"
        if any(k in text for k in ["እሳት", "አደጋ", "fire"]):
            return "Addis Ababa fire disaster Ethiopia"
        if any(k in text for k in ["ትግራይ", "tigray", "መቐለ", "mekelle"]):
            return "Tigray Ethiopia"
        if any(k in text for k in ["አማራ", "amhara", "ጎንደር", "gondar", "ባህር ዳር", "bahir dar"]):
            return "Amhara Ethiopia"
        if any(k in text for k in ["ኦሮሚያ", "oromia", "አዳማ", "adama"]):
            return "Oromia Ethiopia"
        if any(k in text for k in ["ድሬዳዋ", "dire dawa"]):
            return "Dire Dawa Ethiopia"
        if any(k in text for k in ["ሀዋሳ", "ሐዋሳ", "hawassa"]):
            return "Hawassa Ethiopia"
        if any(k in text for k in ["ሶማሌ", "somali", "ጅጅጋ", "jijiga"]):
            return "Somali Region Ethiopia"
        if any(k in text for k in ["አፋር", "afar", "ሰመራ", "semera"]):
            return "Afar Ethiopia"

        if event.primary_region:
            return f"{event.primary_region} Ethiopia"
        if event.primary_category and event.primary_category.lower() not in ["general", "news"]:
            return f"{event.primary_category} Ethiopia"

        return "Addis Ababa Ethiopia"

    def _fetch_wiki_candidates(self, query: str, seen_urls: set[str]) -> list[PhotoCandidate]:
        """Fetch editorial photo candidates from Wikipedia."""
        import urllib.parse
        url = (
            f"https://en.wikipedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote(query)}&gsrlimit=12"
            f"&prop=pageimages|extracts&pithumbsize=1000&exintro=1&explaintext=1&exsentences=2&format=json"
        )
        headers = {
            "User-Agent": "ETHIOTIMESBot/1.0 (editorial-studio@ethiotimes.org; contact: info@ethiotimes.com)"
        }
        candidates: list[PhotoCandidate] = []
        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code != 200:
                    return []
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
        except Exception as exc:
            logger.warning("wiki_candidate_fetch_failed", query=query, error=str(exc))
            return []

        for pid, p in pages.items():
            thumb = p.get("thumbnail", {}).get("source")
            if not thumb or thumb in seen_urls:
                continue
            thumb_lower = thumb.lower()
            if ".svg" in thumb_lower or ".gif" in thumb_lower:
                continue

            title = p.get("title", "Ethiopian Photo")
            extract = p.get("extract", "")

            combined = (title + " " + extract).lower()
            if "ethiopia" not in combined and "addis" not in combined and "amharic" not in combined and "oromo" not in combined and "tigray" not in combined:
                continue

            seen_urls.add(thumb)
            candidates.append(
                PhotoCandidate(
                    id=f"wiki-{pid}",
                    title=title,
                    thumb_url=thumb,
                    image_url=thumb,
                    source="wikimedia",
                    photographer="Wikimedia Commons",
                    description=extract[:140] if extract else None,
                )
            )
        return candidates

    def _fetch_pexels_candidates(self, query: str, api_key: str, seen_urls: set[str]) -> list[PhotoCandidate]:
        """Fetch photo candidates from Pexels."""
        candidates: list[PhotoCandidate] = []
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    "https://api.pexels.com/v1/search",
                    headers={"Authorization": api_key},
                    params={"query": query, "per_page": 6, "orientation": "portrait"},
                )
                if res.status_code == 200:
                    data = res.json()
                    for photo in data.get("photos", []):
                        img_url = photo.get("src", {}).get("portrait") or photo.get("src", {}).get("large")
                        if not img_url or img_url in seen_urls:
                            continue
                        seen_urls.add(img_url)
                        photographer = photo.get("photographer", "Pexels")
                        candidates.append(
                            PhotoCandidate(
                                id=f"pexels-{photo.get('id')}",
                                title=f"Photo by {photographer}",
                                thumb_url=photo.get("src", {}).get("medium") or img_url,
                                image_url=img_url,
                                source="pexels",
                                photographer=photographer,
                                description=f"Editorial photo via Pexels for '{query}'",
                            )
                        )
        except Exception as exc:
            logger.warning("pexels_candidate_fetch_failed", error=str(exc))
        return candidates

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
    def _find_article_image_url(self, event: NewsEvent) -> str | None:
        """Get the first non-null image_url from the event's linked articles."""
        from app.models.article import Article
        from app.models.news_event import EventArticle
        try:
            # 1. Check in-memory relationships if loaded
            if hasattr(event, "article_links") and event.article_links:
                for link in event.article_links:
                    article = getattr(link, "article", None)
                    if article and article.image_url:
                        url = article.image_url.strip()
                        if url.startswith("http"):
                            return url

            # 2. Directly query EventArticle -> Article
            articles = (
                self.session.query(Article)
                .join(EventArticle, EventArticle.article_id == Article.id)
                .filter(EventArticle.event_id == event.id)
                .all()
            )
            for article in articles:
                if article.image_url and article.image_url.strip().startswith("http"):
                    return article.image_url.strip()
        except Exception as exc:
            logger.warning("find_article_image_failed", error=str(exc))
        return None

    def _download_image(self, url: str) -> bytes | None:
        """Download an image and return bytes if it looks valid (>5KB)."""
        try:
            with httpx.Client(timeout=12.0, follow_redirects=True) as client:
                res = client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ETHIOTIMES/1.0"})
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
