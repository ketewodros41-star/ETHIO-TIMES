"""Pure similarity + threshold logic for clustering.

Kept dependency-free and deterministic so it can be unit-tested in isolation
(no DB, no AI). The clustering service composes these with vector search and
optional Gemini confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class ClusterThresholds:
    duplicate: float
    same_event: float
    related: float

    def validate(self) -> None:
        assert 0 < self.related <= self.same_event <= self.duplicate <= 1.0


@dataclass(frozen=True)
class SimilaritySignals:
    cosine: float
    entity_jaccard: float = 0.0
    topic_jaccard: float = 0.0
    category_match: bool = False
    region_match: bool = False


def composite_similarity(s: SimilaritySignals) -> float:
    """Blend cosine similarity with entity/topic/category/region signals.

    Cosine is the dominant term; the other signals provide bounded boosts so that
    strong entity/topic agreement can lift a borderline vector match, but a low
    vector similarity can never be fully rescued. Result is clamped to [0, 1].
    """
    score = 0.75 * s.cosine
    score += 0.12 * s.entity_jaccard
    score += 0.05 * s.topic_jaccard
    score += 0.04 if s.category_match else 0.0
    score += 0.04 if s.region_match else 0.0
    # Normalize back toward cosine when there are no auxiliary signals so a pure
    # high cosine match still scores high.
    if (
        s.entity_jaccard == 0
        and s.topic_jaccard == 0
        and not s.category_match
        and not s.region_match
    ):
        score = s.cosine
    return max(0.0, min(1.0, score))


def classify(score: float, t: ClusterThresholds) -> str:
    """Return relation label for a composite score: duplicate/same_event/related/unrelated."""
    if score >= t.duplicate:
        return "duplicate"
    if score >= t.same_event:
        return "same_event"
    if score >= t.related:
        return "related"
    return "unrelated"


def is_borderline(score: float, t: ClusterThresholds) -> bool:
    """The 'possible same event' band (same_event..duplicate) needs confirmation."""
    return t.same_event <= score < t.duplicate
