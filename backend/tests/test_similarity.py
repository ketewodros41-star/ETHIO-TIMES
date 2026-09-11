"""Unit tests for pure similarity/threshold logic."""

from __future__ import annotations

from app.services.intelligence.similarity import (
    ClusterThresholds,
    SimilaritySignals,
    classify,
    composite_similarity,
    is_borderline,
    jaccard,
)

THRESHOLDS = ClusterThresholds(duplicate=0.90, same_event=0.80, related=0.70)


def test_jaccard():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({"a"}, {"a"}) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_classify_bands():
    assert classify(0.95, THRESHOLDS) == "duplicate"
    assert classify(0.85, THRESHOLDS) == "same_event"
    assert classify(0.72, THRESHOLDS) == "related"
    assert classify(0.50, THRESHOLDS) == "unrelated"


def test_is_borderline_is_the_same_event_band():
    assert is_borderline(0.85, THRESHOLDS) is True
    assert is_borderline(0.95, THRESHOLDS) is False  # duplicate is confident
    assert is_borderline(0.72, THRESHOLDS) is False  # related is not borderline


def test_composite_pure_cosine_when_no_aux_signals():
    s = SimilaritySignals(cosine=0.83)
    assert composite_similarity(s) == 0.83


def test_composite_boosts_with_entity_and_category_overlap():
    base = SimilaritySignals(cosine=0.78)
    boosted = SimilaritySignals(
        cosine=0.78,
        entity_jaccard=1.0,
        topic_jaccard=1.0,
        category_match=True,
        region_match=True,
    )
    assert composite_similarity(boosted) > composite_similarity(base)


def test_composite_is_clamped():
    s = SimilaritySignals(
        cosine=1.0,
        entity_jaccard=1.0,
        topic_jaccard=1.0,
        category_match=True,
        region_match=True,
    )
    assert composite_similarity(s) <= 1.0


def test_low_cosine_cannot_be_fully_rescued():
    s = SimilaritySignals(
        cosine=0.30,
        entity_jaccard=1.0,
        topic_jaccard=1.0,
        category_match=True,
        region_match=True,
    )
    # 0.75*0.30 + 0.12 + 0.05 + 0.04 + 0.04 = 0.475 -> still "unrelated"
    assert classify(composite_similarity(s), THRESHOLDS) == "unrelated"
