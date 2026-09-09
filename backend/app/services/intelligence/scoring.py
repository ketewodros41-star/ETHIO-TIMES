"""Verification scoring engine (Phase 3).

Score 0–100 from source reliability/trust profiles, independent source count,
primary-source availability, coverage diversity, claim consistency, and
contradictions. Maps onto event verification statuses:

    unverified / developing / partially_confirmed / confirmed / contradicted
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.core.config import settings
from app.models.article import Article
from app.models.enums import (
    ContradictionSeverity,
    EventVerificationStatus,
    SourceType,
)
from app.models.news_source import NewsSource
from app.models.verification import EventClaim
from app.services.intelligence.contradiction_service import DetectedContradiction

_TIER_SCORE = {1: 90.0, 2: 70.0, 3: 50.0}

_TYPE_ADJUST = {
    SourceType.national_news_agency: 6.0,
    SourceType.financial_institution: 6.0,
    SourceType.international_wire: 5.0,
    SourceType.government: 4.0,
    SourceType.government_agency: 4.0,
    SourceType.research_institution: 3.0,
    SourceType.public_broadcaster: 2.0,
    SourceType.social_signal: -15.0,
    SourceType.telegram_channel: -10.0,
}

_SEV_PENALTY = {
    ContradictionSeverity.low: 5,
    ContradictionSeverity.medium: 15,
    ContradictionSeverity.high: 25,
    ContradictionSeverity.critical: 40,
}

WEIGHTS = {
    "reliability": 0.25,
    "independent_sources": 0.20,
    "primary_source": 0.15,
    "diversity": 0.15,
    "consistency": 0.15,
    "evidence_coverage": 0.10,
}


@dataclass
class ScoringResult:
    score: int
    status: EventVerificationStatus
    explanation: dict = field(default_factory=dict)


def source_reliability(source: NewsSource) -> float:
    """Map a source's trust_profile + type onto 0–100."""
    profile = source.trust_profile or {}
    tier_raw = profile.get("tier", 2)
    try:
        tier = int(tier_raw)
    except (TypeError, ValueError):
        tier = 2
    score = _TIER_SCORE.get(tier, 70.0)
    if profile.get("editorial_standards") == "high":
        score += 5
    if source.is_primary_source:
        score += 8
    score += _TYPE_ADJUST.get(source.source_type, 0.0)
    return max(0.0, min(100.0, score))


def score_event(
    *,
    articles: list[Article],
    claims: list[EventClaim],
    contradictions: list[DetectedContradiction],
    primary_source_available: bool,
) -> ScoringResult:
    sources = [a.source for a in articles if a.source is not None]
    unique_sources: dict[str, NewsSource] = {str(s.id): s for s in sources}
    reliability_values = [source_reliability(s) for s in unique_sources.values()]
    reliability = (
        sum(reliability_values) / len(reliability_values) if reliability_values else 40.0
    )

    independent = len(unique_sources)
    independent_score = min(independent, 5) / 5.0 * 100.0

    primary_score = 100.0 if primary_source_available else 0.0

    types = {s.source_type.value for s in unique_sources.values()}
    langs = {
        (a.detected_language or a.language or "und") for a in articles
    }
    domains = {_domain(a) for a in articles if _domain(a)}
    diversity = min(
        100.0,
        len(types) * 22.0 + min(len(langs), 3) * 12.0 + min(len(domains), 4) * 8.0,
    )

    major = [c for c in claims if c.is_major]
    evidenced = [c for c in major if c.evidence]
    if not major:
        # No structured claims yet: neither reward nor punish evidence coverage.
        evidence_coverage = 50.0
    else:
        evidence_coverage = 100.0 * len(evidenced) / len(major)

    if not major:
        consistency = 55.0
    elif not contradictions:
        consistency = 100.0
    else:
        worst = max(contradictions, key=lambda x: _SEV_PENALTY[x.severity])
        consistency = max(0.0, 100.0 - _SEV_PENALTY[worst.severity] * 1.5)

    components = {
        "reliability": {
            "score": round(reliability, 1),
            "weight": WEIGHTS["reliability"],
            "detail": f"{independent} unique sources",
        },
        "independent_sources": {
            "score": round(independent_score, 1),
            "weight": WEIGHTS["independent_sources"],
            "detail": f"{independent} independent outlets (cap 5)",
        },
        "primary_source": {
            "score": primary_score,
            "weight": WEIGHTS["primary_source"],
            "detail": "available" if primary_source_available else "not found",
        },
        "diversity": {
            "score": round(diversity, 1),
            "weight": WEIGHTS["diversity"],
            "detail": {
                "source_types": sorted(types),
                "languages": sorted(langs),
                "domains": sorted(domains),
            },
        },
        "consistency": {
            "score": round(consistency, 1),
            "weight": WEIGHTS["consistency"],
            "detail": f"{len(contradictions)} contradiction(s)",
        },
        "evidence_coverage": {
            "score": round(evidence_coverage, 1),
            "weight": WEIGHTS["evidence_coverage"],
            "detail": f"{len(evidenced)}/{len(major)} major claims evidenced",
        },
    }

    raw = sum(
        components[k]["score"] * WEIGHTS[k]  # type: ignore[operator]
        for k in WEIGHTS
    )
    penalties: list[dict] = []
    final = raw
    has_critical = any(
        c.severity == ContradictionSeverity.critical for c in contradictions
    )
    has_high = any(c.severity == ContradictionSeverity.high for c in contradictions)
    if has_critical:
        penalties.append({"reason": "critical contradiction", "cap": 25})
        final = min(final, 25)
    elif has_high:
        penalties.append({"reason": "high-severity contradiction", "delta": -25})
        final -= 25
    elif contradictions:
        penalties.append({"reason": "contradictions present", "delta": -10})
        final -= 10

    score = int(max(0, min(100, round(final))))
    status = _map_status(
        score=score,
        independent=independent,
        contradictions=contradictions,
        has_critical=has_critical,
        has_high=has_high,
    )

    explanation = {
        "components": components,
        "weights": WEIGHTS,
        "raw_score": round(raw, 1),
        "penalties": penalties,
        "final_score": score,
        "status": status.value,
        "independent_source_count": independent,
        "primary_source_available": primary_source_available,
        "claim_count": len(claims),
        "major_claim_count": len(major),
        "evidenced_major_claim_count": len(evidenced),
        "contradiction_count": len(contradictions),
        "contradiction_severities": [c.severity.value for c in contradictions],
    }
    return ScoringResult(score=score, status=status, explanation=explanation)


def _map_status(
    *,
    score: int,
    independent: int,
    contradictions: list[DetectedContradiction],
    has_critical: bool,
    has_high: bool,
) -> EventVerificationStatus:
    if has_critical or has_high:
        return EventVerificationStatus.contradicted
    if contradictions and score < settings.verification_partial_min_score:
        return EventVerificationStatus.contradicted
    if (
        score >= settings.verification_confirmed_min_score
        and independent >= 3
        and not contradictions
    ):
        return EventVerificationStatus.confirmed
    if score >= settings.verification_partial_min_score and independent >= 2:
        return EventVerificationStatus.partially_confirmed
    if score >= settings.verification_developing_min_score or independent >= 1:
        return EventVerificationStatus.developing
    return EventVerificationStatus.unverified


def _domain(article: Article) -> str | None:
    url = article.url or article.canonical_url
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
