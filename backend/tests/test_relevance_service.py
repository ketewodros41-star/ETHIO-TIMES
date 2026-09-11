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
