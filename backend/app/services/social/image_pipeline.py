"""Visual intelligence pipeline (Phase 5, spec §§25-32)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.ai.base import AIProvider, ImageGenerationRequest, ImageProvider
from app.models.enums import VisualAssetStatus
from app.models.news_event import NewsEvent
from app.models.social_post import VisualAsset
from app.repositories.visual_asset_repository import VisualAssetRepository
from app.services.social.editorial_engine import EditorialBrief
from app.services.social.image_critic import ImageCritic, ImageQualityReport
from app.services.social.prompt_engine import PromptEngine
from app.services.social.visual_director import VisualDirector

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

    def run(self, event: NewsEvent, brief: EditorialBrief) -> ImagePipelineResult:
        strategy = self.director.direct(event, brief.headline, brief.short_summary)
        prompt = self.prompt_engine.build_prompt(strategy, event)
        
        all_assets = []
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
                quality_report={"issues": report.issues, "recommendation": report.recommendation},
                status=VisualAssetStatus.generated if report.recommendation == "approve" else VisualAssetStatus.rejected,
                is_selected=False,
            )
            self.asset_repo.create(asset)
            all_assets.append(asset)
            
            if report.overall_score > best_score:
                best_score = report.overall_score
                best_asset = asset
                
            if report.recommendation == "approve" and report.overall_score >= settings.image_quality_threshold:
                break
                
        if best_asset:
            self.asset_repo.mark_selected(best_asset.id)
            
        return ImagePipelineResult(
            selected_asset=best_asset,
            all_assets=all_assets,
            attempts=len(all_assets)
        )
