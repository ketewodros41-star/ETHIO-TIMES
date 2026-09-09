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


def test_generate_carousel_slides():
    provider = FakeAIProvider(available=False)
    engine = EditorialEngine(provider)
    event = NewsEvent(
        title="Economic Reform Signed",
        summary="Ethiopia signs a major economic agreement with international partners.",
        primary_category="economy",
    )
    claim = EventClaim(claim_text="Investment totals 5B USD", claim_type=ClaimType.financial)
    claim.evidence.append(ClaimEvidence(excerpt="5 billion dollars committed", article_id=uuid.uuid4()))
    event.claims.append(claim)

    brief = engine.compose(event)
    assert brief.carousel_slides is not None
    assert len(brief.carousel_slides) >= 3

    # Check slide numbers and total_slides consistency
    total = len(brief.carousel_slides)
    for idx, slide in enumerate(brief.carousel_slides, start=1):
        assert slide["slide_number"] == idx
        assert slide["total_slides"] == total

    # Check cover slide
    assert brief.carousel_slides[0]["slide_type"] == "cover"
    assert brief.carousel_slides[0]["header"] == "Economic Reform Signed"

    # Check key facts slide
    key_facts_slide = next(s for s in brief.carousel_slides if s["slide_type"] == "key_facts")
    assert "Investment totals 5B USD" in key_facts_slide["bullet_points"]


