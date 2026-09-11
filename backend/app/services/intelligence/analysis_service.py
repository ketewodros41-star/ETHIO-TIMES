"""Article analysis (Phase 2).

Language detection, category/subcategory, entity extraction (people, orgs,
companies, government institutions, countries/regions/cities), extracted dates /
money / statistics, topics, and editorial importance. Multilingual by design
(English, Amharic, Afaan Oromo, and others).

Gemini structured JSON is the primary path. A lightweight deterministic fallback
provides at least language detection + a neutral default when the model is
unavailable, so downstream steps still receive a valid ``AnalysisResult``.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderError, TextGenerationRequest
from app.schemas.intelligence import AnalysisResult, Entities
from app.services.intelligence import prompts

logger = get_logger(__name__)

# Map langdetect codes to human names for common Ethiopian-relevant languages.
_LANG_NAMES = {
    "en": "English",
    "am": "Amharic",
    "om": "Afaan Oromo",
    "ti": "Tigrinya",
    "so": "Somali",
    "ar": "Arabic",
    "fr": "French",
}


def detect_language(text: str) -> str:
    """Deterministic language detection; returns ISO code or 'und'."""
    if not text or not text.strip():
        return "und"
    # Amharic/Tigrinya use the Ge'ez (Ethiopic) script: detect by unicode block
    # since langdetect is unreliable on short Ethiopic strings.
    if any("\u1200" <= ch <= "\u137f" for ch in text):
        return "am"
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        return detect(text)
    except Exception:  # noqa: BLE001 - langdetect raises on empty/garbage
        return "und"


class AnalysisService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        *,
        title: str | None,
        summary: str | None,
        content: str | None,
    ) -> tuple[AnalysisResult, bool]:
        """Return (analysis, used_fallback)."""
        if self.provider.is_available():
            try:
                data = self.provider.generate_json(
                    TextGenerationRequest(
                        prompt=prompts.analysis_prompt(title, summary, content),
                        system=prompts.ANALYSIS_SYSTEM,
                        response_schema=prompts.ANALYSIS_SCHEMA,
                        max_tokens=2048,
                    )
                )
                result = AnalysisResult.model_validate(data)
                if not result.language_name:
                    result.language_name = _LANG_NAMES.get(result.language)
                return result, False
            except (ProviderError, ValidationError) as exc:
                logger.warning("analysis_gemini_failed_fallback", error=str(exc))

        return self._fallback(title, summary, content), True

    def _fallback(
        self, title: str | None, summary: str | None, content: str | None
    ) -> AnalysisResult:
        text = " ".join(p for p in (title, summary, content) if p)
        lang = detect_language(text)
        return AnalysisResult(
            language=lang,
            language_name=_LANG_NAMES.get(lang),
            category="general",
            subcategory=None,
            entities=Entities(),
            topics=[],
            importance=50,
            summary=summary,
        )
