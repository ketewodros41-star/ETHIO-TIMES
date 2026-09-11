"""Trend pipeline integration: persist velocity, score, idempotency, Gemini fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.integrations.ai.base import ProviderResponseError
from app.models.enums import ArticleRelationType, TrendStatus
from app.models.news_event import EventArticle, NewsEvent
from app.models.trending import EventVelocityMetric
from app.services.intelligence.trend_pipeline import TrendPipeline
from sqlalchemy import select

from tests.factories import make_article, make_source
from tests.fakes import FakeAIProvider


def _link(session, event: NewsEvent, article, *, relation=ArticleRelationType.primary):
    session.add(
        EventArticle(
            event_id=event.id,
            article_id=article.id,
            relation_type=relation,
            similarity_score=0.9,
            confidence=0.9,
            is_primary=relation == ArticleRelationType.primary,
        )
    )


def test_pipeline_persists_score_and_velocity(db_session):
    now = datetime.now(UTC)
    src_a = make_source(db_session, slug="tr-a")
    src_b = make_source(db_session, slug="tr-b")
    a1 = make_article(db_session, src_a, title="NBE raises rates", published_at=now)
    a2 = make_article(db_session, src_b, title="NBE policy hike", published_at=now)
    event = NewsEvent(
        title="NBE raises the policy rate",
        summary="The National Bank of Ethiopia raised rates.",
        primary_category="economy",
        article_count=2,
        source_count=2,
        last_seen_at=now,
        verification_score=70,
    )
    db_session.add(event)
    db_session.flush()
    _link(db_session, event, a1)
    _link(db_session, event, a2)
    db_session.flush()

    pipeline = TrendPipeline(db_session, FakeAIProvider())
    result = pipeline.process(event, force=True)
    db_session.flush()

    assert result.error is None
    assert result.skipped is False
    assert result.score is not None and result.score > 0
    assert result.status in TrendStatus
    assert "signals" in result.steps_run
    assert event.trend_breakdown["components"]["public_impact"]["detail"]["source"] == "gemini"
    rows = list(
        db_session.scalars(
            select(EventVelocityMetric).where(EventVelocityMetric.event_id == event.id)
        ).all()
    )
    assert {r.window_hours for r in rows} == {1, 6, 24, 72}


def test_pipeline_falls_back_when_gemini_fails(db_session):
    now = datetime.now(UTC)
    src = make_source(db_session, slug="tr-fb")
    article = make_article(db_session, src, title="Drought in Somali region", published_at=now)
    event = NewsEvent(
        title="Drought in Somali region",
        primary_category="disaster",
        article_count=1,
        source_count=1,
        last_seen_at=now,
    )
    db_session.add(event)
    db_session.flush()
    _link(db_session, event, article)
    db_session.flush()

    pipeline = TrendPipeline(
        db_session, FakeAIProvider(raise_on_json=ProviderResponseError("boom"))
    )
    result = pipeline.process(event, force=True)
    assert result.error is None
    assert result.gemini_fallback is True
    assert event.trend_breakdown["gemini_fallback"] is True
    assert event.trend_breakdown["components"]["public_impact"]["detail"]["source"] == "heuristic"


def test_pipeline_unavailable_provider_uses_heuristic(db_session):
    now = datetime.now(UTC)
    src = make_source(db_session, slug="tr-na")
    article = make_article(db_session, src, title="City council meeting", published_at=now)
    event = NewsEvent(
        title="City council meeting",
        article_count=1,
        source_count=1,
        last_seen_at=now,
    )
    db_session.add(event)
    db_session.flush()
    _link(db_session, event, article)
    db_session.flush()

    pipeline = TrendPipeline(db_session, FakeAIProvider(available=False))
    result = pipeline.process(event, force=True)
    assert result.gemini_fallback is True
    assert result.score is not None


def test_pipeline_skips_fresh_rescore(db_session):
    now = datetime.now(UTC)
    src = make_source(db_session, slug="tr-skip")
    article = make_article(db_session, src, title="Skip me", published_at=now)
    event = NewsEvent(
        title="Skip me",
        article_count=1,
        source_count=1,
        last_seen_at=now - timedelta(minutes=10),
        trend_scored_at=now,
        trend_score=41.0,
    )
    db_session.add(event)
    db_session.flush()
    _link(db_session, event, article)
    db_session.flush()

    pipeline = TrendPipeline(db_session, FakeAIProvider())
    result = pipeline.process(event)
    assert result.skipped is True
    forced = pipeline.process(event, force=True)
    assert forced.skipped is False


def test_breaking_candidate_from_velocity_burst(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trend_breaking_min_articles_1h", 3)
    monkeypatch.setattr(settings, "trend_breaking_min_sources_1h", 2)
    now = datetime.now(UTC)
    a = make_source(db_session, slug="tb-a")
    b = make_source(db_session, slug="tb-b")
    articles = [
        make_article(db_session, a, title="flash 1", published_at=now - timedelta(minutes=5)),
        make_article(db_session, a, title="flash 2", published_at=now - timedelta(minutes=8)),
        make_article(db_session, b, title="flash 3", published_at=now - timedelta(minutes=12)),
    ]
    event = NewsEvent(
        title="Flash flood in Dire Dawa",
        primary_category="disaster",
        article_count=3,
        source_count=2,
        last_seen_at=now,
        verification_score=50,
    )
    db_session.add(event)
    db_session.flush()
    for art in articles:
        _link(db_session, event, art)
    db_session.flush()

    pipeline = TrendPipeline(
        db_session,
        FakeAIProvider(
            trend_signals={
                "public_impact": 88,
                "social_momentum": 70,
                "search_interest": 75,
                "breaking_likely": True,
                "reason": "rapid disaster coverage",
                "affected_scope": "regional",
            }
        ),
    )
    result = pipeline.process(event, force=True)
    assert result.breaking_candidate is True
    assert "burst_1h" in event.trend_breakdown["breaking_reasons"]
