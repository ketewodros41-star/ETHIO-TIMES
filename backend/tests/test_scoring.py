"""Scoring engine unit tests (no DB required for the formula)."""

from __future__ import annotations

from app.models.enums import ClaimType, ContradictionSeverity, EventVerificationStatus, SourceType
from app.models.verification import EventClaim
from app.services.intelligence.contradiction_service import DetectedContradiction
from app.services.intelligence.scoring import score_event, source_reliability
from app.services.intelligence.verification_pipeline import _auto_publish_eligible

from tests.factories import make_article, make_source


def test_source_reliability_primary_tier1(db_session):
    src = make_source(
        db_session,
        name="NBE",
        slug="nbe-ethiopia",
        source_type=SourceType.financial_institution,
        is_primary_source=True,
        trust_profile={"tier": 1, "editorial_standards": "high"},
    )
    assert source_reliability(src) >= 90


def test_score_contradicted_on_critical(db_session):
    src_a = make_source(db_session, slug="s1", trust_profile={"tier": 1})
    src_b = make_source(db_session, slug="s2", trust_profile={"tier": 1})
    a1 = make_article(db_session, src_a, title="12 killed in clash")
    a2 = make_article(db_session, src_b, title="3 killed in clash")
    a1.source = src_a
    a2.source = src_b
    ca = EventClaim(
        claim_text="12 killed",
        claim_type=ClaimType.casualty,
        is_major=True,
        confidence=0.8,
    )
    cb = EventClaim(
        claim_text="3 killed",
        claim_type=ClaimType.casualty,
        is_major=True,
        confidence=0.8,
    )
    # Attach dummy evidence collections so coverage isn't zeroed.
    ca.evidence = []
    cb.evidence = []
    conflict = DetectedContradiction(
        claim_a=ca,
        claim_b=cb,
        description="toll",
        severity=ContradictionSeverity.critical,
        source="heuristic",
    )
    result = score_event(
        articles=[a1, a2],
        claims=[ca, cb],
        contradictions=[conflict],
        primary_source_available=False,
    )
    assert result.status == EventVerificationStatus.contradicted
    assert result.score <= 25


def test_auto_publish_blocked_when_sensitive_or_contradicted():
    assert (
        _auto_publish_eligible(
            sensitive=True,
            contradictions=[],
            review_required=True,
            status=EventVerificationStatus.confirmed,
            score=90,
        )
        is False
    )
    assert (
        _auto_publish_eligible(
            sensitive=False,
            contradictions=[object()],  # type: ignore[list-item]
            review_required=False,
            status=EventVerificationStatus.confirmed,
            score=90,
        )
        is False
    )
    assert (
        _auto_publish_eligible(
            sensitive=False,
            contradictions=[],
            review_required=False,
            status=EventVerificationStatus.confirmed,
            score=90,
        )
        is True
    )
