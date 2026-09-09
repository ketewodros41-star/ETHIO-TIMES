from __future__ import annotations

import pytest
from app.models.news_event import NewsEvent
from app.services.social.visual_director import VisualDirector
from tests.fakes import FakeAIProvider


def test_fallback_strategy():
    provider = FakeAIProvider(available=False)
    director = VisualDirector(provider)
    event = NewsEvent(title="Test", primary_category="economy")
    strategy = director._fallback_strategy(event)
    assert strategy.style == "Data-Inspired Visual"
    assert len(strategy.negative_constraints) > 0

