"""Integration tests for the Phase 3 verification pipeline (mocked Gemini)."""

from __future__ import annotations

from app.core.config import settings
from app.models.enums import (
    EventVerificationStatus,
    EventVerifyStatus,
    ProcessingStatus,
)
from app.services.intelligence.evidence_mapping import EvidenceMappingService
from app.services.intelligence.pipeline import IntelligencePipeline
from app.services.intelligence.verification_pipeline import VerificationPipeline

from tests.factories import make_article, make_source
from tests.fakes import FakeAIProvider


def _cluster(db_session, provider, **article_kwargs):  # noqa: ANN001
    source = make_source(db_session)
    article = make_article(db_session, source, **article_kwargs)
    result = IntelligencePipeline(db_session, provider).process(article)
    assert result.final_status == ProcessingStatus.clustered
    assert result.event_id is not None
    return article, result.event_id


def test_verification_extracts_claims_and_persists_score(db_session):
    provider = FakeAIProvider()
    _article, event_id = _cluster(
        db_session,
        provider,
        title="Ethiopia central bank raises interest rates in Addis Ababa",
        summary="The National Bank of Ethiopia raised the policy rate.",
        content="NBE raised the policy rate to 15 percent to curb inflation.",
    )
    from app.models.news_event import NewsEvent

    event = db_session.get(NewsEvent, event_id)
    result = VerificationPipeline(db_session, provider).process(event)
    assert result.skipped is False
    assert result.final_status == EventVerifyStatus.verified
    assert result.claim_count >= 1
    assert event.verification_score >= 0
    assert event.event_verification_status in set(EventVerificationStatus)
    assert event.claims
    assert all(c.evidence for c in event.claims)
    # Default fake analysis category is politics → human review, never auto-publish.
    assert event.review_required is True
    assert event.auto_publish_eligible is False
    assert event.verification_explanation.get("final_score") == event.verification_score


def test_verification_is_idempotent_until_new_coverage(db_session):
    provider = FakeAIProvider()
    _article, event_id = _cluster(
        db_session,
        provider,
        title="Ethiopia Addis Ababa policy rate decision",
        summary="NBE update",
        content="policy rate Ethiopia",
    )
    from app.models.news_event import NewsEvent

    event = db_session.get(NewsEvent, event_id)
    first = VerificationPipeline(db_session, provider).process(event)
    assert first.skipped is False
    second = VerificationPipeline(db_session, provider).process(event)
    assert second.skipped is True


def test_conflicting_casualty_counts_contradict_and_block_publish(db_session):
    # Fallback extraction will pull 12 vs 3 killed from copy.
    src_a = make_source(db_session, slug="wire-a")
    src_b = make_source(db_session, slug="wire-b")
    shared = (
        "Ethiopia Oromia clash security incident Addis Ababa regional conflict "
        "military operation civilians"
    )
    # Need embeddings, so use a provider that can embed but we'll run verification
    # with fallback-only claims by making generate_json unavailable... Fake with
    # available True for clustering, then verify with available False.
    cluster_provider = FakeAIProvider()
    a1 = make_article(
        db_session,
        src_a,
        title=shared + " 12 people killed",
        summary=shared + " 12 people killed",
        content=shared + " 12 people killed near the town.",
    )
    a2 = make_article(
        db_session,
        src_b,
        title=shared + " 3 people killed",
        summary=shared + " 3 people killed",
        content=shared + " 3 people killed near the town.",
    )
    p = IntelligencePipeline(db_session, cluster_provider)
    r1 = p.process(a1)
    r2 = p.process(a2)
    assert r1.event_id == r2.event_id
    from app.models.news_event import NewsEvent

    event = db_session.get(NewsEvent, r1.event_id)
    result = VerificationPipeline(db_session, FakeAIProvider(available=False)).process(
        event
    )
    assert result.contradiction_count >= 1
    assert event.event_verification_status == EventVerificationStatus.contradicted
    assert event.review_required is True
    assert event.auto_publish_eligible is False
    assert any(c.severity.value in {"high", "critical"} for c in event.contradictions)


def test_primary_source_flag_when_nbe_cited(db_session):
    from app.models.enums import SourceType

    make_source(
        db_session,
        slug="nbe-ethiopia",
        name="National Bank of Ethiopia (NBE)",
        source_type=SourceType.financial_institution,
        is_primary_source=True,
        trust_profile={"tier": 1},
    )
    provider = FakeAIProvider()
    _article, event_id = _cluster(
        db_session,
        provider,
        title="Ethiopia National Bank of Ethiopia raises policy rate Addis Ababa",
        summary="The National Bank of Ethiopia announced a hike.",
        content="According to the National Bank of Ethiopia the policy rate is 15%.",
    )
    from app.models.news_event import NewsEvent

    event = db_session.get(NewsEvent, event_id)
    VerificationPipeline(db_session, provider).process(event)
    assert event.primary_source_available is True
    assert event.cited_institutions


def test_verification_dead_letters_after_repeated_failure(db_session, monkeypatch):
    monkeypatch.setattr(settings, "verification_max_attempts", 1)

    def _boom(self, *args, **kwargs):  # noqa: ANN001
        raise RuntimeError("persist failed")

    monkeypatch.setattr(EvidenceMappingService, "persist_bundle", _boom)

    provider = FakeAIProvider()
    _article, event_id = _cluster(
        db_session,
        provider,
        title="Ethiopia Addis Ababa economic policy update",
        summary="content",
        content="Ethiopia policy",
    )
    db_session.commit()
    from app.models.news_event import NewsEvent

    event = db_session.get(NewsEvent, event_id)
    result = VerificationPipeline(db_session, provider).process(event)
    assert result.final_status == EventVerifyStatus.dead_letter
    refreshed = db_session.get(NewsEvent, event_id)
    assert refreshed.verification_attempts >= 1
    assert refreshed.last_verification_error is not None
