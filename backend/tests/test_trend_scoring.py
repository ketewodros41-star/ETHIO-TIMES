"""Trend scoring unit tests (formula + status mapping; no live Gemini)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.enums import TrendStatus
from app.models.news_event import NewsEvent
from app.schemas.intelligence import TrendSignals
from app.services.intelligence.trend_scoring import (
    combine_trend_score,
    map_trend_status,
    recency_score,
    trend_weights,
)
from app.services.intelligence.velocity import VelocitySnapshot


def test_weights_sum_to_one():
    weights = trend_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["recency"] == 0.20
    assert weights["velocity"] == 0.20
    assert weights["diversity"] == 0.15
    assert weights["public_impact"] == 0.20
    assert weights["social_momentum"] == 0.10
    assert weights["search_interest"] == 0.10
    assert weights["editorial_importance"] == 0.05


def test_recency_decays_with_age():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    fresh = NewsEvent(title="fresh", last_seen_at=now - timedelta(minutes=20))
    day = NewsEvent(title="day", last_seen_at=now - timedelta(hours=20))
    week = NewsEvent(title="week", last_seen_at=now - timedelta(days=8))
    s_fresh, _ = recency_score(fresh, now=now)
    s_day, _ = recency_score(day, now=now)
    s_week, _ = recency_score(week, now=now)
    assert s_fresh > s_day > s_week
    assert s_fresh >= 95
    assert s_week <= 10


def test_map_status_breaking_requires_score_or_impact():
    assert (
        map_trend_status(score=70, breaking=True, public_impact=40)
        == TrendStatus.breaking
    )
    assert (
        map_trend_status(score=40, breaking=True, public_impact=80)
        == TrendStatus.breaking
    )
    assert map_trend_status(score=85, breaking=False, public_impact=40) == (
        TrendStatus.high_priority
    )
    assert map_trend_status(score=65, breaking=False, public_impact=40) == (
        TrendStatus.trending
    )
    assert map_trend_status(score=45, breaking=False, public_impact=40) == (
        TrendStatus.emerging
    )
    assert map_trend_status(score=10, breaking=False, public_impact=10) == TrendStatus.low


def test_combine_includes_component_breakdown():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    event = NewsEvent(
        title="NBE rate decision",
        last_seen_at=now - timedelta(minutes=30),
        article_count=4,
        source_count=3,
        verification_score=70,
        primary_category="economy",
    )
    snapshots = {
        1: VelocitySnapshot(1, 2, 2, 2.0, 2.0),
        6: VelocitySnapshot(6, 4, 3, 1.2, 0.66),
        24: VelocitySnapshot(24, 4, 3, 1.0, 0.16),
        72: VelocitySnapshot(72, 4, 3, 1.0, 0.05),
    }
    result = combine_trend_score(
        event=event,
        articles=[],
        snapshots=snapshots,
        velocity=55.0,
        velocity_detail={"articles_1h": 2},
        editorial_importance=70.0,
        editorial_detail={"score": 70},
        signals=TrendSignals(),
        used_gemini_fallback=True,
        heuristic_breaking_reasons=[],
        now=now,
    )
    components = result.breakdown["components"]
    for key in (
        "recency",
        "velocity",
        "diversity",
        "public_impact",
        "social_momentum",
        "search_interest",
        "editorial_importance",
    ):
        assert key in components
        assert "score" in components[key]
        assert "weight" in components[key]
    assert result.breakdown["weights"] == trend_weights()
    assert 0 <= result.score <= 100
    assert result.status in TrendStatus
