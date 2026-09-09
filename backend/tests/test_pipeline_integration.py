"""Integration tests for the intelligence pipeline (DB + mocked Gemini)."""

from __future__ import annotations

from app.core.config import settings
from app.models.enums import ProcessingStatus
from app.repositories.event_repository import EventRepository
from app.services.intelligence.pipeline import IntelligencePipeline

from tests.factories import make_article, make_source
from tests.fakes import FakeAIProvider, RateLimitedProvider


def test_full_pipeline_relevant_article_gets_clustered(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="Ethiopia announces new economic policy",
        summary="The government outlined reforms in Addis Ababa.",
        content="Ethiopia policy content about the economy and reforms.",
    )
    pipeline = IntelligencePipeline(db_session, FakeAIProvider())
    result = pipeline.process(article)

    assert result.final_status == ProcessingStatus.clustered
    assert result.steps_run == ["relevance", "analysis", "embedding", "cluster"]
    assert article.analysis is not None
    assert article.embedding is not None
    assert article.relevance_score == 88
    assert result.event_id is not None


def test_pipeline_is_idempotent(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session, source, title="Ethiopia news", summary="Addis Ababa update"
    )
    pipeline = IntelligencePipeline(db_session, FakeAIProvider())
    first = pipeline.process(article)
    assert first.final_status == ProcessingStatus.clustered

    # Re-running does no work (already terminal); no new steps, same event.
    second = pipeline.process(article)
    assert second.final_status == ProcessingStatus.clustered
    assert second.steps_run == []


def test_irrelevant_article_is_skipped(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="Local French election result",
        summary="Unrelated content",
    )
    provider = FakeAIProvider(
        relevance={
            "is_ethiopia_related": False,
            "score": 10,
            "reason": "not Ethiopia",
            "categories": [],
        }
    )
    result = IntelligencePipeline(db_session, provider).process(article)
    assert result.final_status == ProcessingStatus.skipped_irrelevant
    assert article.analysis is None
    assert article.embedding is None


def test_pipeline_stops_after_analysis_without_provider(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="Ethiopia Addis Ababa Abiy Ahmed policy update",
        summary="GERD milestone",
    )
    # Provider unavailable: relevance + analysis use fallbacks, embedding can't run.
    result = IntelligencePipeline(db_session, FakeAIProvider(available=False)).process(
        article
    )
    assert result.final_status == ProcessingStatus.analyzed
    assert article.analysis is not None
    assert article.embedding is None


def test_pipeline_dead_letters_after_repeated_failure(db_session, monkeypatch):
    monkeypatch.setattr(settings, "pipeline_max_attempts", 1)
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="Ethiopia Addis Ababa economic policy",
        summary="content",
    )
    # Persist first (mirrors production, where ingestion commits before the
    # pipeline runs) so the pipeline's internal rollback doesn't remove the row.
    db_session.commit()
    # Embedding raises a rate-limit error that is not recoverable here.
    result = IntelligencePipeline(db_session, RateLimitedProvider()).process(article)
    assert result.final_status == ProcessingStatus.dead_letter
    refreshed = db_session.get(type(article), article.id)
    assert refreshed.processing_attempts >= 1
    assert refreshed.processing_error is not None


def test_two_similar_articles_form_one_event(db_session):
    source_a = make_source(db_session, slug="src-a")
    source_b = make_source(db_session, slug="src-b")
    shared = (
        "Ethiopia central bank raises interest rates to curb inflation in Addis Ababa "
        "economy policy monetary birr"
    )
    a1 = make_article(db_session, source_a, title=shared, summary=shared, content=shared)
    a2 = make_article(
        db_session,
        source_b,
        title=shared + " reform",
        summary=shared,
        content=shared,
    )
    pipeline = IntelligencePipeline(db_session, FakeAIProvider())
    r1 = pipeline.process(a1)
    r2 = pipeline.process(a2)

    assert r1.event_id is not None
    assert r2.event_id == r1.event_id  # clustered into the same event

    events = EventRepository(db_session)
    event = events.get_detail(r1.event_id)
    assert event.article_count == 2
    assert event.source_count == 2
    assert len(event.article_links) == 2
