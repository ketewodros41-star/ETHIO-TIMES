"""Unit tests for relevance detection: scoring, thresholds, and fallback."""

from __future__ import annotations

from app.core.config import settings
from app.models.enums import RelevanceDecision
from app.services.intelligence.relevance_service import RelevanceService, decide

from tests.fakes import FakeAIProvider


def test_decide_bands():
    thr = settings.relevance_threshold
    margin = settings.relevance_borderline_margin
    assert decide(thr) == RelevanceDecision.relevant
    assert decide(thr + 10) == RelevanceDecision.relevant
    assert decide(thr - 1) == RelevanceDecision.borderline
    assert decide(thr - margin) == RelevanceDecision.borderline
    assert decide(thr - margin - 1) == RelevanceDecision.irrelevant


def test_relevant_via_provider():
    provider = FakeAIProvider(
        relevance={
            "is_ethiopia_related": True,
            "score": 92,
            "primary_region": "Tigray",
            "reason": "about Ethiopia",
            "categories": ["politics"],
        }
    )
    svc = RelevanceService(provider)
    out = svc.assess(title="Ethiopia news", summary=None, content=None)
    assert out.used_fallback is False
    assert out.decision == RelevanceDecision.relevant
    assert out.result.score == 92
    assert out.result.primary_region == "Tigray"


def test_borderline_via_provider():
    score = settings.relevance_threshold - 5
    provider = FakeAIProvider(
        relevance={
            "is_ethiopia_related": True,
            "score": score,
            "reason": "maybe",
            "categories": [],
        }
    )
    out = RelevanceService(provider).assess(title="x", summary=None, content=None)
    assert out.decision == RelevanceDecision.borderline


def test_fallback_when_provider_unavailable_uses_keywords():
    provider = FakeAIProvider(available=False)
    svc = RelevanceService(provider)
    out = svc.assess(
        title="Addis Ababa and Abiy Ahmed announce GERD milestone",
        summary=None,
        content=None,
    )
    assert out.used_fallback is True
    assert out.result.score >= settings.relevance_threshold
    assert out.decision == RelevanceDecision.relevant


def test_fallback_irrelevant_for_unrelated_text():
    provider = FakeAIProvider(available=False)
    out = RelevanceService(provider).assess(
        title="French elections update", summary=None, content=None
    )
    assert out.used_fallback is True
    assert out.decision == RelevanceDecision.irrelevant


def test_fallback_when_provider_raises():
    from app.integrations.ai.base import ProviderResponseError

    provider = FakeAIProvider(raise_on_json=ProviderResponseError("boom"))
    out = RelevanceService(provider).assess(
        title="Ethiopia economy", summary=None, content=None
    )
    assert out.used_fallback is True


def test_monitored_international_source_is_relevant():
    from unittest.mock import MagicMock
    from app.models.enums import SourceType

    source = MagicMock()
    source.name = "Al Jazeera"
    source.slug = "al-jazeera"
    source.country = "QA"
    source.source_type = SourceType.international_media
    source.coverage_categories = ["international", "world"]

    provider = FakeAIProvider(available=False)
    out = RelevanceService(provider).assess(
        title="More than 100,000 displaced in Yemen conflict",
        summary="A humanitarian crisis unfolds in Yemen.",
        content=None,
        source=source,
    )
    assert out.decision == RelevanceDecision.relevant
    assert out.result.is_ethiopia_related is False
    assert out.result.primary_region == "International"
    assert out.result.score >= settings.relevance_threshold


def test_monitored_sports_source_is_relevant():
    from unittest.mock import MagicMock
    from app.models.enums import SourceType

    source = MagicMock()
    source.name = "Sports Desk"
    source.slug = "sports"
    source.country = "ET"
    source.source_type = SourceType.telegram_channel
    source.coverage_categories = ["sports", "football"]

    provider = FakeAIProvider(available=False)
    out = RelevanceService(provider).assess(
        title="Haaland scores twice as Man City beats Man Utd 2-1",
        summary="Premier League matchweek 4 highlights and table updates.",
        content=None,
        source=source,
    )
    assert out.decision == RelevanceDecision.relevant
    assert out.result.is_ethiopia_related is False
    assert "sports" in out.result.categories
    assert out.result.score >= settings.relevance_threshold


def test_monitored_international_with_ethiopia_keywords():
    from unittest.mock import MagicMock
    from app.models.enums import SourceType

    source = MagicMock()
    source.name = "CNN"
    source.slug = "cnn"
    source.country = "US"
    source.source_type = SourceType.international_media
    source.coverage_categories = ["international"]

    provider = FakeAIProvider(available=False)
    out = RelevanceService(provider).assess(
        title="African Union summit convenes in Addis Ababa to discuss regional peace",
        summary="Leaders gather in Ethiopia for the 37th ordinary session.",
        content=None,
        source=source,
    )
    assert out.decision == RelevanceDecision.relevant
    assert out.result.is_ethiopia_related is True
    assert out.result.primary_region in ("Addis Ababa", "Ethiopia", "addis ababa")

