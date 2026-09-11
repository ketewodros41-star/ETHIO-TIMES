"""Unit tests for structured AI contract parsing / coercion."""

from __future__ import annotations

import pytest
from app.schemas.intelligence import (
    AnalysisResult,
    ClaimExtractionResult,
    ClusterRelation,
    ContradictionDetectionResult,
    Entities,
    ExtractedClaim,
    RelevanceResult,
)
from pydantic import ValidationError


def test_relevance_clamps_and_coerces():
    r = RelevanceResult(
        is_ethiopia_related=True, score="150.7", reason="x", categories="politics"
    )
    assert r.score == 100
    assert r.categories == ["politics"]


def test_relevance_negative_score_clamped():
    r = RelevanceResult(is_ethiopia_related=False, score=-5, reason="x")
    assert r.score == 0


def test_relevance_requires_bool():
    with pytest.raises(ValidationError):
        RelevanceResult(score=50)  # missing is_ethiopia_related


def test_analysis_defaults_and_importance_clamp():
    a = AnalysisResult(language="en", importance="999")
    assert a.importance == 100
    assert a.category == "general"
    assert isinstance(a.entities, Entities)


def test_entities_all_names_dedup_lowercase():
    e = Entities(
        people=["Abiy Ahmed", "abiy ahmed"],
        countries=["Ethiopia"],
        cities=["Addis Ababa"],
    )
    names = e.all_names()
    assert "abiy ahmed" in names
    assert names.count("abiy ahmed") == 1
    assert "ethiopia" in names


def test_cluster_relation_normalizes_invalid():
    c = ClusterRelation(relation="NONSENSE", confidence=0.5)
    assert c.relation == "unrelated"
    c2 = ClusterRelation(relation="Same_Event", confidence=0.9)
    assert c2.relation == "same_event"


def test_extracted_claim_normalizes_type_and_confidence():
    c = ExtractedClaim(
        claim_text="NBE hiked rates",
        claim_type="FINANCIAL",
        confidence="1.4",
        entities="NBE",
        excerpt="NBE hiked rates to 15%",
    )
    assert c.claim_type == "financial"
    assert c.confidence == 1.0
    assert c.entities == ["NBE"]


def test_extracted_claim_unknown_type_becomes_announcement():
    c = ExtractedClaim(claim_text="x", claim_type="rumour")
    assert c.claim_type == "announcement"


def test_claim_extraction_result_coerces_institutions():
    r = ClaimExtractionResult(cited_institutions="NBE")
    assert r.cited_institutions == ["NBE"]
    assert r.claims == []


def test_contradiction_result_normalizes_severity():
    r = ContradictionDetectionResult(
        contradictions=[
            {
                "claim_a_index": 0,
                "claim_b_index": 1,
                "description": "toll differs",
                "severity": "CRITICAL",
            }
        ]
    )
    assert r.contradictions[0].severity == "critical"
