"""Editorial importance for an event (Phase 4).

Combines per-article analysis importance, category/entity prominence, and
verification signals into a 0–100 score that feeds the trend-weight mix
(``editorial_importance`` = 5%).
"""

from __future__ import annotations

from app.models.article import Article
from app.models.enums import ClaimType
from app.models.news_event import NewsEvent
from app.models.verification import EventClaim
from app.services.intelligence.sensitive_rules import SENSITIVE_CATEGORIES

# Category tokens → editorial weight (0–100). Sensitive / high-stakes desks
# outrank lifestyle/sports so they can still surface when velocity is modest.
_CATEGORY_SCORE: dict[str, float] = {
    "conflict": 92,
    "war": 94,
    "military": 88,
    "deaths": 90,
    "disaster": 90,
    "disasters": 90,
    "elections": 86,
    "politics": 80,
    "political": 80,
    "policy": 74,
    "economy": 76,
    "economic": 76,
    "finance": 74,
    "financial": 74,
    "health": 78,
    "public_safety": 88,
    "ethnic": 85,
    "religion": 82,
    "crime": 70,
    "diplomacy": 68,
    "business": 60,
    "sports": 35,
    "entertainment": 30,
    "general": 45,
}

_PROMINENT_NEEDLES = (
    "abiy",
    "prime minister",
    "pmo",
    "national bank",
    "nbe",
    "ministry of finance",
    "mofa",
    "mfa",
    "endf",
    "tplf",
    "oromia",
    "tigray",
    "amhara",
    "addis ababa",
    "federal",
)


def score_editorial_importance(
    event: NewsEvent,
    articles: list[Article],
    claims: list[EventClaim] | None = None,
) -> tuple[float, dict]:
    """Return (score 0–100, breakdown dict)."""
    claims = claims or []
    analysis_scores = [
        float(a.analysis.importance)
        for a in articles
        if a.analysis is not None and a.analysis.importance is not None
    ]
    article_scores = [
        float(a.importance_score)
        for a in articles
        if a.importance_score and a.importance_score > 0
    ]
    if analysis_scores:
        mean_analysis = sum(analysis_scores) / len(analysis_scores)
        source = "article_analysis.importance"
    elif article_scores:
        mean_analysis = sum(article_scores) / len(article_scores)
        source = "articles.importance_score"
    else:
        mean_analysis = 50.0
        source = "default"

    category_score = _category_score(event, articles)
    entity_score = _entity_prominence(event, articles)
    verification = float(event.verification_score or 0)
    primary_boost = 100.0 if event.primary_source_available else 0.0
    casualty_boost = (
        100.0 if any(c.claim_type == ClaimType.casualty for c in claims) else 0.0
    )

    raw = (
        0.45 * mean_analysis
        + 0.20 * category_score
        + 0.15 * entity_score
        + 0.12 * verification
        + 0.04 * primary_boost
        + 0.04 * casualty_boost
    )
    score = max(0.0, min(100.0, round(raw, 1)))
    detail = {
        "score": score,
        "mean_analysis_importance": round(mean_analysis, 1),
        "analysis_source": source,
        "category_score": round(category_score, 1),
        "entity_prominence": round(entity_score, 1),
        "verification_score": verification,
        "primary_source_available": bool(event.primary_source_available),
        "casualty_claims": casualty_boost > 0,
    }
    return score, detail


def _category_score(event: NewsEvent, articles: list[Article]) -> float:
    tokens: list[str] = []
    if event.primary_category:
        tokens.append(event.primary_category.lower())
    tokens.extend(str(c).lower() for c in (event.categories or []))
    for article in articles:
        if article.analysis and article.analysis.category:
            tokens.append(article.analysis.category.lower())
        if article.analysis and article.analysis.subcategory:
            tokens.append(article.analysis.subcategory.lower())
        tokens.extend(str(t).lower() for t in (article.analysis.topics if article.analysis else []))

    best = 45.0
    for token in tokens:
        for key, value in _CATEGORY_SCORE.items():
            if key in token:
                best = max(best, value)
        for sensitive_key in SENSITIVE_CATEGORIES:
            if sensitive_key in token:
                best = max(best, 82.0)
    return best


def _entity_prominence(event: NewsEvent, articles: list[Article]) -> float:
    names: list[str] = [str(n).lower() for n in (event.key_entities or [])]
    gov = 0
    people = 0
    for article in articles:
        if not article.analysis:
            continue
        ents = article.analysis.entities or {}
        if isinstance(ents, dict):
            gov += len(ents.get("government_institutions") or [])
            people += len(ents.get("people") or [])
            names.extend(str(n).lower() for n in (article.analysis.entity_names or []))
    blob = " ".join(names)
    prominent = sum(1 for needle in _PROMINENT_NEEDLES if needle in blob)
    return max(
        0.0,
        min(100.0, prominent * 18.0 + min(gov, 4) * 10.0 + min(people, 4) * 6.0),
    )
