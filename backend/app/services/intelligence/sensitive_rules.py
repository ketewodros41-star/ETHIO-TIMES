"""Sensitive-news rules (Phase 3).

Politics, conflict, military, deaths, crime, ethnic tension, religion,
elections, public safety, financial panic, and disasters default to human
review and are never auto-published.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.article import Article
from app.models.news_event import NewsEvent

# category/topic tokens (lowercase) that trip the sensitive gate
SENSITIVE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "politics": ("politics", "political", "governance", "government"),
    "conflict": ("conflict", "war", "clash", "fighting", "insurgent", "insurgency"),
    "military": ("military", "army", "defence", "defense", "airstrike", "endf"),
    "deaths": ("death", "deaths", "killed", "casualty", "casualties", "fatal"),
    "crime": ("crime", "murder", "homicide", "arrest", "trial", "prison"),
    "ethnic": ("ethnic", "ethnicity", "tribe", "communal"),
    "religion": ("religion", "religious", "church", "mosque", "orthodox", "islam"),
    "elections": ("election", "elections", "ballot", "electoral", "vote", "voting"),
    "public_safety": (
        "public safety",
        "emergency",
        "evacuation",
        "hostage",
        "terror",
        "bomb",
    ),
    "financial_panic": (
        "bank run",
        "bank-run",
        "devaluation panic",
        "currency collapse",
        "market crash",
        "default",
        "hyperinflation",
    ),
    "disasters": (
        "earthquake",
        "flood",
        "drought",
        "famine",
        "landslide",
        "epidemic",
        "outbreak",
        "disaster",
    ),
}


@dataclass
class SensitiveVerdict:
    sensitive: bool
    categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def evaluate_sensitive(event: NewsEvent, articles: list[Article]) -> SensitiveVerdict:
    tokens: list[str] = []
    if event.primary_category:
        tokens.append(event.primary_category)
    tokens.extend(event.categories or [])
    tokens.extend(event.key_entities or [])
    if event.title:
        tokens.append(event.title)
    if event.summary:
        tokens.append(event.summary)

    for article in articles:
        tokens.append(article.title or "")
        tokens.append(article.summary or "")
        if article.analysis:
            if article.analysis.category:
                tokens.append(article.analysis.category)
            if article.analysis.subcategory:
                tokens.append(article.analysis.subcategory)
            tokens.extend(article.analysis.topics or [])

    blob = " ".join(tokens).lower()
    hit_categories: list[str] = []
    reasons: list[str] = []
    for category, needles in SENSITIVE_CATEGORIES.items():
        for needle in needles:
            if needle in blob:
                hit_categories.append(category)
                reasons.append(f"sensitive:{category}:{needle}")
                break

    return SensitiveVerdict(
        sensitive=bool(hit_categories),
        categories=hit_categories,
        reasons=reasons,
    )
