"""Ethiopia relevance detection (Phase 2).

Primary path uses Gemini structured JSON; when the provider is unavailable or
fails, a deterministic keyword heuristic is used so the pipeline degrades
gracefully (and CI never needs a live model). The decision (relevant /
borderline / irrelevant) is computed from a configurable threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProvider,
    ProviderError,
    TextGenerationRequest,
)
from app.models.enums import RelevanceDecision
from app.pipelines.relevance import score_relevance
from app.schemas.intelligence import RelevanceResult
from app.services.intelligence import prompts

logger = get_logger(__name__)


@dataclass
class RelevanceOutcome:
    result: RelevanceResult
    decision: RelevanceDecision
    used_fallback: bool


def decide(score: int) -> RelevanceDecision:
    """Map a 0-100 score to a decision using configured threshold + margin."""
    threshold = settings.relevance_threshold
    margin = settings.relevance_borderline_margin
    if score >= threshold:
        return RelevanceDecision.relevant
    if score >= threshold - margin:
        return RelevanceDecision.borderline
    return RelevanceDecision.irrelevant


class RelevanceService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def assess(
        self,
        *,
        title: str | None,
        summary: str | None,
        content: str | None,
    ) -> RelevanceOutcome:
        if self.provider.is_available():
            try:
                data = self.provider.generate_json(
                    TextGenerationRequest(
                        prompt=prompts.relevance_prompt(title, summary, content),
                        system=prompts.RELEVANCE_SYSTEM,
                        response_schema=prompts.RELEVANCE_SCHEMA,
                        max_tokens=512,
                    )
                )
                result = RelevanceResult.model_validate(data)
                return RelevanceOutcome(result, decide(result.score), used_fallback=False)
            except (ProviderError, ValidationError) as exc:
                logger.warning("relevance_gemini_failed_fallback", error=str(exc))

        return self._fallback(title, summary, content)

    def _fallback(
        self, title: str | None, summary: str | None, content: str | None
    ) -> RelevanceOutcome:
        raw_score, keywords = score_relevance(title, summary, content)
        score = int(round(raw_score * 100))
        result = RelevanceResult(
            is_ethiopia_related=score >= settings.relevance_threshold,
            score=score,
            primary_region=None,
            reason=(
                f"Keyword fallback matched: {', '.join(keywords)}"
                if keywords
                else "Keyword fallback: no Ethiopia keywords matched"
            ),
            categories=[],
        )
        return RelevanceOutcome(result, decide(score), used_fallback=True)
