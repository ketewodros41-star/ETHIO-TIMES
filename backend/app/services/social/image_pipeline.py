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
        """Try to fetch a real photo from the event's linked articles."""
        image_url = self._find_article_image_url(event)
        if not image_url:
            logger.info("no_article_image_url", event_id=str(event.id))
            # Fall back to AI generation with a minimal brief
            from app.services.social.editorial_engine import EditorialBrief
            brief = EditorialBrief(
                headline=event.title,
                short_summary=event.summary or "",
                key_facts=[],
                hashtags=[],
                caption="",
                theme="verified_brief",
            )
            return self.run(event, brief)

        image_bytes = self._download_image(image_url)
        if not image_bytes:
            logger.warning("article_image_download_failed", url=image_url)
            from app.services.social.editorial_engine import EditorialBrief
            brief = EditorialBrief(
                headline=event.title,
                short_summary=event.summary or "",
                key_facts=[],
                hashtags=[],
                caption="",
                theme="verified_brief",
            )
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
    # Public entry: Pexels photo search
    # ------------------------------------------------------------------
    def search_pexels(self, event: NewsEvent, query: str | None = None) -> list[VisualAsset]:
        """Search Pexels for editorial photos matching the story. Returns list of assets."""
        pexels_key = getattr(settings, "pexels_api_key", None)
        if not pexels_key:
            logger.warning("pexels_not_configured")
            return []

        # Build a smart search query from event context
        if not query:
            query = self._build_pexels_query(event)

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(
                    "https://api.pexels.com/v1/search",
                    headers={"Authorization": pexels_key},
                    params={"query": query, "per_page": 6, "orientation": "portrait"},
                )
                if res.status_code != 200:
                    logger.warning("pexels_error", status=res.status_code)
                    return []

                data = res.json()
                photos = data.get("photos", [])

        except Exception as exc:
            logger.warning("pexels_request_failed", error=str(exc))
            return []

        assets = []
        for photo in photos[:6]:
            image_url = photo.get("src", {}).get("portrait") or photo.get("src", {}).get("large")
            if not image_url:
                continue

            image_bytes = self._download_image(image_url)
            if not image_bytes:
                continue

            photographer = photo.get("photographer", "Pexels")
            asset = VisualAsset(
                event_id=event.id,
                prompt=f"Pexels search: {query}",
                visual_strategy={"strategy": "pexels_photo", "pexels_id": photo.get("id")},
                provider="pexels",
                model=f"Pexels/{photographer}",
                style="Real Editorial Photo",
                quality_score=80,
                quality_report={
                    "image_source": "pexels",
                    "pexels_id": photo.get("id"),
                    "photographer": photographer,
                    "pexels_url": photo.get("url"),
                    "query": query,
                    "issues": [],
                    "recommendation": "approve",
                },
                status=VisualAssetStatus.generated,
                is_selected=False,
            )
            self.asset_repo.create(asset)
            asset = self._persist_image(asset, image_bytes, None)
            assets.append(asset)

        return assets

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_article_image_url(self, event: NewsEvent) -> str | None:
        """Get the first non-null image_url from the event's linked articles."""
        try:
            for link in event.article_links:
                article = link.article
                if article and article.image_url:
                    url = article.image_url.strip()
                    if url.startswith("http"):
                        return url
        except Exception as exc:
            logger.warning("find_article_image_failed", error=str(exc))
        return None

    def _download_image(self, url: str) -> bytes | None:
        """Download an image and return bytes if it looks valid (>5KB)."""
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                res = client.get(url, headers={"User-Agent": "ETHIOTIMES/1.0 editorial-studio"})
                if res.status_code == 200 and len(res.content) > 5000:
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
