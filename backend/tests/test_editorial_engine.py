from __future__ import annotations

import uuid

import pytest
from app.models.enums import ClaimType, TrendStatus
from app.models.news_event import NewsEvent
from app.models.verification import ClaimEvidence, EventClaim
from app.services.social.editorial_engine import EditorialEngine
from tests.fakes import FakeAIProvider


def test_compose_with_fallback():
    provider = FakeAIProvider(available=False)
    engine = EditorialEngine(provider)
    event = NewsEvent(
        title="Test Event",
        summary="Summary",
        primary_category="economy",
        trend_score=80.0,
    )
    claim = EventClaim(claim_text="Facts", claim_type=ClaimType.financial)
    claim.evidence.append(ClaimEvidence(excerpt="Evidence text", article_id=uuid.uuid4()))
    event.claims.append(claim)

    brief = engine.compose(event)
    assert brief.headline == "Test Event"
    assert "Facts" in brief.key_facts
    assert brief.suggested_theme == "economy"


def test_auto_theme_breaking():
    provider = FakeAIProvider(available=False)
    engine = EditorialEngine(provider)
    event = NewsEvent(title="Breaking Event", trend_status=TrendStatus.breaking)
    assert engine._auto_theme(event) == "breaking"

