"""Contract tests for layout-safe Amharic editorial translation."""
from __future__ import annotations

import pytest

from app.integrations.ai.base import AIProvider, TextGenerationRequest
from app.schemas.social_post import EditorialTranslationRequest
from app.services.social.translation_service import (
    EditorialTranslationService,
    TranslationUnavailableError,
)


class TranslationProvider(AIProvider):
    name = "translation-test"

    def __init__(self, payload: dict, available: bool = True) -> None:
        self.payload = payload
        self.available = available
        self.requests: list[TextGenerationRequest] = []

    def is_available(self) -> bool:
        return self.available

    def generate_json(self, request: TextGenerationRequest) -> dict:
        self.requests.append(request)
        return self.payload

    def embed(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        return [[0.0] for _ in texts]


def _service(payload: dict, available: bool = True) -> tuple[EditorialTranslationService, TranslationProvider]:
    provider = TranslationProvider(payload, available)
    return EditorialTranslationService(None, provider), provider  # type: ignore[arg-type]


def test_single_card_translation_requires_amharic_and_valid_highlight():
    service, provider = _service(
        {
            "headline": "ብሔራዊ ባንክ አዲስ መመሪያ አወጣ",
            "dek": "መመሪያው የውጭ ምንዛሬ ሥርዓትን ለማሻሻል ያተኮረ ነው።",
            "category": "ኢኮኖሚ",
            "punchline_words": ["አዲስ", "አወጣ"],
        }
    )

    result = service.translate_editorial(
        EditorialTranslationRequest(
            headline="National Bank issues a new directive",
            dek="The directive focuses on foreign exchange reform.",
        )
    )

    assert result.status == "ready"
    assert result.provider == "translation-test"
    assert result.slide_headers == []
    assert "EVENT TITLE" not in provider.requests[0].prompt
    assert result.layout_budget["headline_max_chars"] == 68


def test_translation_rejects_english_fallback_and_invalid_highlight():
    service, _ = _service(
        {
            "headline": "National Bank issues directive",
            "dek": "This is not an Amharic translation.",
            "category": "News",
            "punchline_words": ["missing"],
        }
    )

    with pytest.raises(TranslationUnavailableError):
        service.translate_editorial(EditorialTranslationRequest(headline="National Bank issues directive"))


def test_carousel_requires_five_distinct_translated_slides():
    headers = ["ዋና ዜና", "ምን ተፈጠረ", "ቁልፍ ነጥቦች", "ለምን ያስፈልጋል", "ምንጮች"]
    bodies = [
        "ብሔራዊ ባንክ አዲስ መመሪያ አወጣ።",
        "መመሪያው የውጭ ምንዛሬ ገበያን ያሻሽላል።",
        "ባንኩ ዋና የፖሊሲ ለውጦችን አስታውቋል።",
        "ለድርጅቶችና ለቤተሰቦች ቀጥተኛ ተፅዕኖ ይኖረዋል።",
        "መረጃው ከተረጋገጡ ምንጮች ተሰብስቧል።",
    ]
    service, provider = _service(
        {
            "headline": "ብሔራዊ ባንክ መመሪያ አወጣ",
            "dek": "አዲሱ መመሪያ የውጭ ምንዛሬ ሥርዓትን ያሻሽላል።",
            "category": "ኢኮኖሚ",
            "punchline_words": ["መመሪያ"],
            "slide_headers": headers,
            "slide_bodies": bodies,
        }
    )

    result = service.translate_editorial(
        EditorialTranslationRequest(
            headline="National Bank issues directive",
            template="carousel",
            content_mode="carousel_5",
            slide_headers=["What happened"],
            slide_bodies=["The central bank issued a directive."],
        )
    )

    assert result.slide_headers == headers
    assert len(result.slide_bodies) == 5
    assert "EXISTING CAROUSEL COPY" in provider.requests[0].prompt
