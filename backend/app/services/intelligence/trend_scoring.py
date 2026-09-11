"""Weighted trend scoring (Phase 4).

Components (configurable, defaults shown):

    recency 20% · velocity 20% · diversity 15% · public impact 20%
    social momentum 10% · search interest 10% · editorial importance 5%

Each component is 0–100. The weighted sum is persisted as ``trend_score`` with
a JSON breakdown. Statuses: low / emerging / trending / high_priority / breaking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderError, TextGenerationRequest
from app.models.article import Article
from app.models.enums import SourceType, TrendStatus
from app.models.news_event import NewsEvent
from app.schemas.intelligence import TrendSignals
from app.services.intelligence import prompts
from app.services.intelligence.sensitive_rules import evaluate_sensitive
from app.services.intelligence.velocity import VelocitySnapshot

logger = get_logger(__name__)


def trend_weights() -> dict[str, float]:
    return {
        "recency": settings.trend_recency_weight,
        "velocity": settings.trend_velocity_weight,
        "diversity": settings.trend_diversity_weight,
        "public_impact": settings.trend_public_impact_weight,
        "social_momentum": settings.trend_social_momentum_weight,
        "search_interest": settings.trend_search_interest_weight,
        "editorial_importance": settings.trend_editorial_importance_weight,
    }


@dataclass
class TrendScoreResult:
    score: float
    status: TrendStatus
    breaking_candidate: bool
    breakdown: dict = field(default_factory=dict)


def recency_score(
    event: NewsEvent, *, now: datetime | None = None
) -> tuple[float, dict]:
    now = now or datetime.now(UTC)
    ts = event.last_seen_at or event.updated_at or event.created_at
    if ts is None:
        return 5.0, {"hours_ago": None, "reason": "no timestamp"}
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    if hours <= 1:
        score = 100.0
    elif hours <= 6:
        score = 100.0 - (hours - 1) / 5.0 * 20.0  # 100 → 80
    elif hours <= 24:
        score = 80.0 - (hours - 6) / 18.0 * 25.0  # 80 → 55
    elif hours <= 72:
        score = 55.0 - (hours - 24) / 48.0 * 25.0  # 55 → 30
    elif hours <= 168:
        score = 30.0 - (hours - 72) / 96.0 * 20.0  # 30 → 10
    else:
        score = 5.0
    return round(score, 1), {"hours_ago": round(hours, 2)}


def diversity_score(articles: list[Article]) -> tuple[float, dict]:
    sources = [a.source for a in articles if a.source is not None]
    unique = {str(s.id): s for s in sources}
    types = {s.source_type.value for s in unique.values()}
    langs = {(a.detected_language or a.language or "und") for a in articles}
    domains = {_domain(a) for a in articles if _domain(a)}
    score = min(
        100.0,
        len(unique) * 12.0
        + len(types) * 16.0
        + min(len(langs), 4) * 8.0
        + min(len(domains), 5) * 6.0,
    )
    return round(score, 1), {
        "unique_sources": len(unique),
        "source_types": sorted(types),
        "languages": sorted(langs),
        "domains": sorted(domains),
    }


def heuristic_public_impact(
    event: NewsEvent, articles: list[Article]
) -> tuple[float, dict]:
    sensitive = evaluate_sensitive(event, articles)
    high_stakes = {
        "conflict",
        "military",
        "deaths",
        "disasters",
        "elections",
        "public_safety",
        "financial_panic",
        "ethnic",
    }
    score = 35.0
    if sensitive.sensitive:
        if any(c in high_stakes for c in sensitive.categories):
            score = 82.0
        else:
            score = 68.0
    if event.primary_source_available:
        score += 8.0
    score += min(15.0, (event.verification_score or 0) * 0.15)
    score += min(10.0, (event.source_count or 0) * 2.0)
    return max(0.0, min(100.0, round(score, 1))), {
        "sensitive_categories": sensitive.categories,
        "primary_source_available": bool(event.primary_source_available),
        "source": "heuristic",
    }


def heuristic_social_momentum(
    articles: list[Article], snapshots: dict[int, VelocitySnapshot]
) -> tuple[float, dict]:
    sources = [a.source for a in articles if a.source is not None]
    types = {s.source_type for s in sources}
    socialish = {SourceType.social_signal, SourceType.telegram_channel}
    international = {SourceType.international_media, SourceType.international_wire}
    score = 18.0
    if types & socialish:
        score += 28.0
    if types & international:
        score += 18.0
    w1 = snapshots.get(1)
    if w1:
        score += min(30.0, w1.article_count * 10.0)
        score += min(16.0, w1.unique_source_count * 6.0)
    return max(0.0, min(100.0, round(score, 1))), {
        "source_types": sorted(t.value for t in types),
        "source": "heuristic",
    }


def heuristic_search_interest(
    event: NewsEvent, articles: list[Article], editorial_importance: float
) -> tuple[float, dict]:
    score = 0.45 * editorial_importance + 0.25 * min(100.0, (event.article_count or 0) * 8.0)
    blob = " ".join(
        [
            event.title or "",
            event.summary or "",
            " ".join(str(x) for x in (event.key_entities or [])),
            event.primary_category or "",
        ]
    ).lower()
    if any(
        needle in blob
        for needle in ("abiy", "nbe", "election", "killed", "crash", "devaluation")
    ):
        score += 18.0
    if event.primary_category and event.primary_category.lower() in {
        "politics",
        "conflict",
        "economy",
        "finance",
    }:
        score += 12.0
    return max(0.0, min(100.0, round(score, 1))), {"source": "heuristic"}


def assess_trend_signals(
    provider: AIProvider,
    event: NewsEvent,
    articles: list[Article],
) -> tuple[TrendSignals, bool]:
    """Gemini public-impact / social / search signals; heuristic on failure."""
    if provider.is_available():
        try:
            data = provider.generate_json(
                TextGenerationRequest(
                    prompt=prompts.trend_signals_prompt(event, articles),
                    system=prompts.TREND_SIGNALS_SYSTEM,
                    response_schema=prompts.TREND_SIGNALS_SCHEMA,
                    max_tokens=512,
                )
            )
            return TrendSignals.model_validate(data), False
        except (ProviderError, ValidationError) as exc:
            logger.warning("trend_signals_gemini_failed_fallback", error=str(exc))
    return TrendSignals(), True


def combine_trend_score(
    *,
    event: NewsEvent,
    articles: list[Article],
    snapshots: dict[int, VelocitySnapshot],
    velocity: float,
    velocity_detail: dict,
    editorial_importance: float,
    editorial_detail: dict,
    signals: TrendSignals,
    used_gemini_fallback: bool,
    heuristic_breaking_reasons: list[str],
    now: datetime | None = None,
) -> TrendScoreResult:
    recency, recency_detail = recency_score(event, now=now)
    diversity, diversity_detail = diversity_score(articles)
    h_impact, impact_h = heuristic_public_impact(event, articles)
    h_social, social_h = heuristic_social_momentum(articles, snapshots)
    h_search, search_h = heuristic_search_interest(event, articles, editorial_importance)

    if used_gemini_fallback:
        public_impact, impact_detail = h_impact, impact_h
        social_momentum, social_detail = h_social, social_h
        search_interest, search_detail = h_search, search_h
    else:
        public_impact = float(signals.public_impact)
        social_momentum = float(signals.social_momentum)
        search_interest = float(signals.search_interest)
        impact_detail = {
            "source": "gemini",
            "reason": signals.reason,
            "affected_scope": signals.affected_scope,
            "heuristic": h_impact,
        }
        social_detail = {"source": "gemini", "heuristic": h_social}
        search_detail = {"source": "gemini", "heuristic": h_search}

    weights = trend_weights()
    components = {
        "recency": {"score": recency, "weight": weights["recency"], "detail": recency_detail},
        "velocity": {
            "score": velocity,
            "weight": weights["velocity"],
            "detail": velocity_detail,
        },
        "diversity": {
            "score": diversity,
            "weight": weights["diversity"],
            "detail": diversity_detail,
        },
        "public_impact": {
            "score": public_impact,
            "weight": weights["public_impact"],
            "detail": impact_detail,
        },
        "social_momentum": {
            "score": social_momentum,
            "weight": weights["social_momentum"],
            "detail": social_detail,
        },
        "search_interest": {
            "score": search_interest,
            "weight": weights["search_interest"],
            "detail": search_detail,
        },
        "editorial_importance": {
            "score": editorial_importance,
            "weight": weights["editorial_importance"],
            "detail": editorial_detail,
        },
    }
    raw = sum(components[k]["score"] * weights[k] for k in weights)  # type: ignore[operator]
    score = max(0.0, min(100.0, round(float(raw), 1)))

    breaking_reasons = list(heuristic_breaking_reasons)
    if not used_gemini_fallback and signals.breaking_likely and velocity >= 50:
        breaking_reasons.append("gemini_breaking_likely")
    breaking = bool(breaking_reasons)
    status = map_trend_status(score=score, breaking=breaking, public_impact=public_impact)

    breakdown = {
        "components": components,
        "weights": weights,
        "raw_score": round(float(raw), 1),
        "final_score": score,
        "status": status.value,
        "breaking_candidate": breaking,
        "breaking_reasons": breaking_reasons,
        "gemini_fallback": used_gemini_fallback,
        "scored_at": (now or datetime.now(UTC)).isoformat(),
    }
    return TrendScoreResult(
        score=score,
        status=status,
        breaking_candidate=breaking,
        breakdown=breakdown,
    )


def map_trend_status(
    *, score: float, breaking: bool, public_impact: float
) -> TrendStatus:
    if breaking and (
        score >= settings.trend_breaking_min_score or public_impact >= 70
    ):
        return TrendStatus.breaking
    if score >= settings.trend_status_high_priority_min:
        return TrendStatus.high_priority
    if breaking:
        # Burst detected but the composite is still modest — keep it visible.
        if score >= settings.trend_status_trending_min:
            return TrendStatus.trending
        return TrendStatus.emerging
    if score >= settings.trend_status_trending_min:
        return TrendStatus.trending
    if score >= settings.trend_status_emerging_min:
        return TrendStatus.emerging
    return TrendStatus.low


def _domain(article: Article) -> str | None:
    url = article.url or article.canonical_url
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None
