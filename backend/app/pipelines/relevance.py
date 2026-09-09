"""Ethiopia-relevance scoring — Phase 1 keyword heuristic.

This is a deliberately simple keyword/heuristic stub. The real relevance
classifier (a Gemini-based filter with context and reasoning) is Phase 2. The
interface — `score_relevance(text) -> (score, matched_keywords)` — is stable so
the pipeline can swap in the AI classifier later without changing callers.
"""

from __future__ import annotations

import re

# Non-exhaustive keyword set covering Ethiopian places, institutions, and
# frequently-referenced entities. Lowercased; matched on word boundaries.
_KEYWORDS: tuple[str, ...] = (
    "ethiopia",
    "ethiopian",
    "addis ababa",
    "addis abeba",
    "oromia",
    "amhara",
    "tigray",
    "afar",
    "somali region",
    "sidama",
    "abiy ahmed",
    "prosperity party",
    "ena",
    "national bank of ethiopia",
    "birr",
    "ethiopian airlines",
    "grand ethiopian renaissance dam",
    "gerd",
    "nile",
    "horn of africa",
    "eritrea",
    "dire dawa",
    "hawassa",
    "bahir dar",
    "mekelle",
    "adama",
)

_COMPILED = [(kw, re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)) for kw in _KEYWORDS]


def score_relevance(*text_parts: str | None) -> tuple[float, list[str]]:
    """Return (score in [0,1], matched_keywords) for the concatenated text.

    Scoring is a saturating function of the number of distinct keyword matches;
    a single strong match ("ethiopia") already yields high relevance.
    """
    haystack = " ".join(p for p in text_parts if p).lower()
    if not haystack:
        return 0.0, []

    matched = [kw for kw, pattern in _COMPILED if pattern.search(haystack)]
    if not matched:
        return 0.0, []

    # Saturating score: 1 match -> 0.6, 2 -> 0.8, 3 -> 0.9, 4+ -> ~1.0
    distinct = len(matched)
    score = min(1.0, 0.6 + 0.2 * (distinct - 1))
    return round(score, 3), matched
