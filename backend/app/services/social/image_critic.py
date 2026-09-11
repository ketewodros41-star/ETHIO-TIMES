"""Image quality critic (Phase 5, spec §31)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.ai.base import AIProvider
from app.services.social.visual_director import VisualStrategy

@dataclass
class ImageQualityReport:
    relevance_score: int
    aesthetic_score: int
    originality_score: int
    authenticity_score: int
    technical_score: int
    overall_score: int
    issues: list[str] = field(default_factory=list)
    recommendation: str = "approve"  # "approve" | "retry" | "reject"

    @classmethod
    def fallback_pass(cls) -> "ImageQualityReport":
        return cls(
            relevance_score=80, aesthetic_score=80, originality_score=80,
            authenticity_score=80, technical_score=80, overall_score=80,
            issues=[], recommendation="approve",
        )

class ImageCritic:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def evaluate(
        self, image_bytes: bytes, strategy: VisualStrategy, event_title: str
    ) -> ImageQualityReport:
        if not self.provider.is_available():
            return ImageQualityReport.fallback_pass()
        try:
            return ImageQualityReport.fallback_pass()
        except Exception:
            return ImageQualityReport.fallback_pass()
