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


def is_monitored_intl_or_sports_source(source: object | None) -> bool:
    """Check if the source is an international or sports feed explicitly monitored by ETHIO-TIMES."""
    if source is None:
        return False
    country = (getattr(source, "country", "") or "").upper()
    source_type = getattr(source, "source_type", None)
    type_str = str(source_type.value if hasattr(source_type, "value") else source_type or "").lower()
    if type_str in ("international_wire", "international_media") or (country and country != "ET"):
        return True
    slug = (getattr(source, "slug", "") or "").lower()
    name = (getattr(source, "name", "") or "").lower()
    categories = [str(c).lower() for c in (getattr(source, "coverage_categories", None) or [])]
    if any(c in ("international", "world", "global", "sports", "football", "soccer") for c in categories):
        return True
    intl_sport_cues = [
        "cnn", "al-jazeera", "al jazeera", "reuters", "dw-africa", "bbc-africa",
        "ap-news", "ap news", "sports", "sport", "football", "premier league",
    ]
    return any(cue in slug or cue in name for cue in intl_sport_cues)


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
        # Fast-path 1: Check deterministic Ethiopian keyword score first
        fast_score, fast_keywords = score_relevance(title, summary, content)
        country = (getattr(source, "country", "") or "").upper() if source else ""
        
        # High confidence Ethiopian match (score >= 75 or verified ET source with keywords)
        if fast_score >= 75 or (country == "ET" and fast_keywords):
            res = RelevanceResult(
                score=max(fast_score, 85),
                is_ethiopia_related=True,
                reason=f"Direct high-confidence keyword match: {', '.join(fast_keywords[:5])}",
                primary_region=fast_keywords[0] if fast_keywords else "Ethiopia",
            )
            return RelevanceOutcome(res, RelevanceDecision.relevant, used_fallback=True)

        # Fast-path 2: Monitored international or sports source
        # If the platform intentionally ingests this source, it is relevant for international / sports coverage
        if is_monitored_intl_or_sports_source(source):
            src_name = getattr(source, "name", "International source")
            categories = [str(c).lower() for c in (getattr(source, "coverage_categories", None) or [])]
            primary_cat = "sports" if any("sport" in c or "football" in c for c in categories) or "sport" in (getattr(source, "slug", "") or "").lower() else "international"
            res = RelevanceResult(
                score=85,
                is_ethiopia_related=bool(fast_keywords),
                reason=f"Monitored {primary_cat} source ({src_name})",
                primary_region="Ethiopia" if fast_keywords else "International",
                categories=[primary_cat],
            )
            return RelevanceOutcome(res, RelevanceDecision.relevant, used_fallback=True)

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
            if is_monitored_intl_or_sports_source(source):
                src_name = getattr(source, "name", "International source")
                categories = [str(c).lower() for c in (getattr(source, "coverage_categories", None) or [])]
                primary_cat = "sports" if any("sport" in c or "football" in c for c in categories) or "sport" in (getattr(source, "slug", "") or "").lower() else "international"
                result = RelevanceResult(
                    is_ethiopia_related=bool(keywords),
                    score=85,
                    primary_region="Ethiopia" if keywords else "International",
                    reason=f"Monitored {primary_cat} source ({src_name})",
                    categories=[primary_cat],
                )
                return RelevanceOutcome(result, RelevanceDecision.relevant, used_fallback=True)

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
