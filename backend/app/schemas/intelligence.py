"""Typed contracts for the intelligence pipeline (Phase 2).

These Pydantic models define the *structured JSON* the Gemini provider must
return. They are used both as response schemas (to constrain generation) and to
validate/parse responses. Keeping them strict means a malformed AI response is
rejected and the deterministic fallback (where applicable) takes over.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Relevance
# --------------------------------------------------------------------------- #
class RelevanceResult(BaseModel):
    is_ethiopia_related: bool = Field(
        ..., description="Whether the article is meaningfully about Ethiopia."
    )
    score: int = Field(..., ge=0, le=100, description="Confidence 0-100.")
    primary_region: str | None = Field(
        default=None,
        description="Primary Ethiopian region/city if applicable, else null.",
    )
    reason: str = Field(default="", description="Short justification.")
    categories: list[str] = Field(
        default_factory=list, description="High-level topical categories."
    )

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v: object) -> int:
        try:
            n = int(round(float(v)))  # tolerate float scores
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, n))

    @field_validator("categories", mode="before")
    @classmethod
    def _coerce_categories(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v]  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
class Entities(BaseModel):
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    government_institutions: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)

    def all_names(self) -> list[str]:
        """Flat, de-duplicated, lowercased list of all entity names."""
        seen: dict[str, None] = {}
        for group in (
            self.people,
            self.organizations,
            self.companies,
            self.government_institutions,
            self.countries,
            self.regions,
            self.cities,
        ):
            for name in group:
                key = name.strip().lower()
                if key:
                    seen.setdefault(key, None)
        return list(seen.keys())


class MoneyMention(BaseModel):
    amount: str
    currency: str | None = None
    context: str | None = None


class StatMention(BaseModel):
    value: str
    unit: str | None = None
    context: str | None = None


class DateMention(BaseModel):
    text: str
    iso: str | None = None
    context: str | None = None


class AnalysisResult(BaseModel):
    language: str = Field(default="und", description="ISO 639-1/3 language code.")
    language_name: str | None = None
    category: str = Field(default="general")
    subcategory: str | None = None
    entities: Entities = Field(default_factory=Entities)
    dates: list[DateMention] = Field(default_factory=list)
    money: list[MoneyMention] = Field(default_factory=list)
    statistics: list[StatMention] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    importance: int = Field(default=50, ge=0, le=100)
    summary: str | None = None

    @field_validator("importance", mode="before")
    @classmethod
    def _clamp_importance(cls, v: object) -> int:
        try:
            n = int(round(float(v)))
        except (TypeError, ValueError):
            return 50
        return max(0, min(100, n))

    @field_validator("topics", mode="before")
    @classmethod
    def _coerce_topics(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v]  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Clustering confirmation (borderline only)
# --------------------------------------------------------------------------- #
class ClusterRelation(BaseModel):
    """Gemini's verdict on whether two articles cover the same event."""

    relation: str = Field(
        default="unrelated",
        description="One of: duplicate, same_event, related, unrelated.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")

    @field_validator("relation", mode="before")
    @classmethod
    def _norm_relation(cls, v: object) -> str:
        s = str(v or "").strip().lower()
        allowed = {"duplicate", "same_event", "related", "unrelated"}
        return s if s in allowed else "unrelated"
