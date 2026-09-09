"""Unit tests for the Ethiopia relevance keyword heuristic."""

from __future__ import annotations

from app.pipelines.relevance import score_relevance


def test_no_match_scores_zero():
    score, matched = score_relevance("A story about French politics")
    assert score == 0.0
    assert matched == []


def test_single_keyword_scores_high():
    score, matched = score_relevance("Ethiopia announces new policy")
    assert score >= 0.6
    assert "ethiopia" in matched


def test_multiple_keywords_increase_score():
    single, _ = score_relevance("Addis Ababa news")
    multi, matched = score_relevance(
        "Abiy Ahmed visits Addis Ababa to discuss the GERD on the Nile"
    )
    assert multi > single
    assert len(matched) >= 3


def test_score_saturates_at_one():
    text = "Ethiopia Ethiopian Addis Ababa Oromia Amhara Tigray Abiy Ahmed birr GERD Nile"
    score, _ = score_relevance(text)
    assert score <= 1.0
