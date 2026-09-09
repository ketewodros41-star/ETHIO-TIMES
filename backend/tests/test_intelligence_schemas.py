"""Unit tests for structured AI contract parsing / coercion."""

from __future__ import annotations

import pytest
from app.schemas.intelligence import (
    AnalysisResult,
    ClusterRelation,
    Entities,
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
