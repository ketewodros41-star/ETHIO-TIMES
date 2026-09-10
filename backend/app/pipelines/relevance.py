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
    # ----- Core Ethiopia terms -----
    "ethiopia", "ethiopian", "ethiopians",
    "addis ababa", "addis abeba",
    "fdre", "federal democratic republic of ethiopia",
    
    # ----- Administrative regions -----
    "oromia", "oromo", "afaan oromo",
    "amhara", "amhara region",
    "tigray", "tigrayans", "tplf", "mekele", "mekelle",
    "afar", "afar region", "semera",
    "somali region", "jijiga",
    "sidama", "hawassa",
    "snnpr",
    "benishangul-gumuz", "assosa",
    "gambella",
    "harari", "harar",
    "central ethiopia", "southwest ethiopia",
    
    # ----- Major cities -----
    "dire dawa", "gondar", "jimma", "bahir dar",
    "adama", "nazret", "nekemte", "bishoftu",
    "debre birhan", "debre markos", "woldia", "kombolcha",
    "dilla", "shashamene", "arba minch", "bale",
    "axum", "aksum", "lalibela",
    
    # ----- Government & politics -----
    "abiy ahmed", "prosperity party",
    "eprdf", "sahle-work zewde", "sahle-work",
    "ethiopian parliament", "house of peoples representatives",
    "addis ababa city administration",
    "national bank of ethiopia", "nbe",
    "ethiopian revenues and customs authority",
    "ethiopia's prime minister", "pm abiy",
    
    # ----- Military & security -----
    "endf", "ethiopian national defense force",
    "ethiopian federal police", "amhara fano", "fano",
    "abiy", "olf-ola", "oromo liberation army",
    
    # ----- Economy & business -----
    "ethiopian birr", "birr",
    "ethiopian airlines",
    "metec", "ethiopian electric power", "eep",
    "industrial park", "bole lemi", "hawassa industrial",
    "gerd", "grand ethiopian renaissance dam", "abbay dam", "abbay river",
    "blue nile", "nile treaty", "nile negotiations",
    "effort",
    
    # ----- Media & institutions -----
    "ebc", "ethiopian broadcasting corporation",
    "ena", "ethiopian news agency",
    "ehrc", "ethiopian human rights commission",
    "addis fortune", "addis standard", "reporter ethiopia",
    "addis ababa university",
    "ethiopian orthodox", "eotc",
    
    # ----- Diaspora terms -----
    "habesha", "ethiopian american", "ethiopian diaspora",
    "ethio-american", "ethiopian community",
    "ethiopian restaurant", "ethiopian coffee",
    "enkutatash", "ethiopian new year",
    "timkat", "meskel", "genna", "fasika",
    "ethiopian calendar",
    "ethiopian orthodox church",
    "ethio-diaspora", "little ethiopia",
    
    # ----- Cultural/language signals -----
    "amharic", "tigrinya", "afaan oromo",
    "injera", "teff", "tej", "berbere",
    "habesha kemis", "habesha dress",
    "ethiopian coffee ceremony",
    "adey abeba",
    
    # ----- Horn of Africa (conditional) -----
    "horn of africa", "eritrea", "eritrean",
    "djibouti", "djiboutian",
    "igad", "intergovernmental authority on development",
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
