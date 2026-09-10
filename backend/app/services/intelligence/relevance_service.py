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
        source: object | None = None,
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

                # Source-level boost for verified Ethiopian outlets
                if source is not None:
                    country = (getattr(source, "country", "") or "").upper()
                    rel_score = float(getattr(source, "ethiopia_relevance_score", 0.0) or 0.0)
                    if (country == "ET" or rel_score >= 0.8) and result.score < settings.relevance_threshold:
                        raw_score, keywords = score_relevance(title, summary, content)
                        if keywords:
                            result.score = max(result.score, 85)
                            result.is_ethiopia_related = True
                            result.reason = f"Verified Ethiopian source ({getattr(source, 'name', 'source')}) with keyword match: {', '.join(keywords)}"

                return RelevanceOutcome(result, decide(result.score), used_fallback=False)
            except (ProviderError, ValidationError) as exc:
                logger.warning("relevance_gemini_failed_fallback", error=str(exc))

        return self._fallback(title, summary, content, source=source)

    def _fallback(
        self,
        title: str | None,
        summary: str | None,
        content: str | None,
        source: object | None = None,
    ) -> RelevanceOutcome:
        raw_score, keywords = score_relevance(title, summary, content)
        score = int(round(raw_score * 100))

        # Check source-level heuristics for Ethiopian sources
        if source is not None:
            country = (getattr(source, "country", "") or "").upper()
            rel_score = float(getattr(source, "ethiopia_relevance_score", 0.0) or 0.0)
            if (country == "ET" or rel_score >= 0.8) and score < settings.relevance_threshold:
                text_combined = f"{title or ''} {summary or ''} {content or ''}"
                has_geez = any("\u1200" <= ch <= "\u137f" for ch in text_combined)
                if keywords or has_geez:
                    score = max(score, 85)
                    source_name = getattr(source, "name", "Ethiopian source")
                    keywords.append(f"source:{source_name}")

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
