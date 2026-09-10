from __future__ import annotations

from app.models.news_event import NewsEvent
from app.services.social.visual_director import VisualDirector
from tests.fakes import FakeAIProvider


def test_direct_strategy_economy():
    """VisualDirector.direct() should return a strategy with economy style for economy events."""
    provider = FakeAIProvider(available=False)
    director = VisualDirector(provider)
    event = NewsEvent(title="Ethiopia raises $2B Eurobond", primary_category="economy")
    strategy = director.direct(event, event.title, "")
    # Economy category maps to "Premium Editorial Magazine" or "Data-Inspired Visual"
    assert strategy.style in ("Premium Editorial Magazine", "Data-Inspired Visual", "Bloomberg editorial photography")
    assert len(strategy.negative_constraints) > 0
    assert strategy.story_context is not None


def test_direct_strategy_politics():
    """Political events should produce a portrait-angle cinematic strategy."""
    provider = FakeAIProvider(available=False)
    director = VisualDirector(provider)
    event = NewsEvent(title="PM Abiy meets EU envoy", primary_category="politics")
    strategy = director.direct(event, event.title, "diplomatic meeting in Addis Ababa")
    assert strategy.story_context is not None
    assert len(strategy.negative_constraints) > 0


def test_direct_always_returns_strategy():
    """direct() should never raise — always returns a valid VisualStrategy."""
    provider = FakeAIProvider(available=False)
    director = VisualDirector(provider)
    event = NewsEvent(title="", primary_category=None)
    strategy = director.direct(event, "untitled", "")
    assert strategy is not None
    assert strategy.style

