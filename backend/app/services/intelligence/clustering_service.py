"""Duplicate detection + event clustering (Phase 2).

Combines vector cosine similarity with entity overlap, publication-time
proximity, and geography/category/topic agreement to decide whether a new
article belongs with an existing one (and thus its event). Gemini confirmation
is used only for borderline (possible same-event) pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderError, TextGenerationRequest
from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.schemas.intelligence import ClusterRelation
from app.services.intelligence import prompts
from app.services.intelligence.similarity import (
    ClusterThresholds,
    SimilaritySignals,
    classify,
    composite_similarity,
    is_borderline,
    jaccard,
)

logger = get_logger(__name__)


@dataclass
class ClusterMatch:
    article: Article
    cosine: float
    composite: float
    relation: str  # duplicate | same_event | related | unrelated
    confidence: float
    source: str  # "heuristic" | "gemini"


def _signals_for(article: Article) -> tuple[set[str], set[str], str | None, str | None]:
    """Return (entity_names, topics, category, region) for an article."""
    entities: set[str] = set()
    topics: set[str] = set()
    category: str | None = None
    if article.analysis is not None:
        entities = {str(e).lower() for e in (article.analysis.entity_names or [])}
        topics = {str(t).lower() for t in (article.analysis.topics or [])}
        category = article.analysis.category
    region = (article.primary_region or "").lower() or None
    return entities, topics, category, region


class ClusteringService:
    def __init__(self, session, provider: AIProvider) -> None:  # noqa: ANN001
        self.session = session
        self.provider = provider
        self.articles = ArticleRepository(session)
        self.thresholds = ClusterThresholds(
            duplicate=settings.cluster_duplicate_threshold,
            same_event=settings.cluster_same_event_threshold,
            related=settings.cluster_related_threshold,
        )

    def find_best_match(self, article: Article) -> ClusterMatch | None:
        if article.embedding is None:
            return None

        window_start = datetime.now(UTC) - timedelta(
            hours=settings.cluster_time_window_hours
        )
        neighbors = self.articles.nearest_by_embedding(
            article.embedding,
            limit=settings.cluster_candidate_limit,
            exclude_id=article.id,
            published_after=window_start,
        )
        if not neighbors:
            return None

        a_entities, a_topics, a_category, a_region = _signals_for(article)

        best: ClusterMatch | None = None
        for candidate, cosine in neighbors:
            b_entities, b_topics, b_category, b_region = _signals_for(candidate)
            signals = SimilaritySignals(
                cosine=cosine,
                entity_jaccard=jaccard(a_entities, b_entities),
                topic_jaccard=jaccard(a_topics, b_topics),
                category_match=bool(a_category and a_category == b_category),
                region_match=bool(a_region and a_region == b_region),
            )
            composite = composite_similarity(signals)
            relation = classify(composite, self.thresholds)
            if relation == "unrelated":
                continue
            match = ClusterMatch(
                article=candidate,
                cosine=cosine,
                composite=composite,
                relation=relation,
                confidence=composite,
                source="heuristic",
            )
            if best is None or match.composite > best.composite:
                best = match

        if best is None:
            return None

        # Borderline (possible same event) → confirm with Gemini if available.
        if is_borderline(best.composite, self.thresholds) and self.provider.is_available():
            confirmed = self._confirm(article, best)
            if confirmed is not None:
                return confirmed
        return best

    def _confirm(self, article: Article, match: ClusterMatch) -> ClusterMatch | None:
        try:
            data = self.provider.generate_json(
                TextGenerationRequest(
                    prompt=prompts.cluster_prompt(
                        {"title": article.title, "summary": article.summary},
                        {"title": match.article.title, "summary": match.article.summary},
                    ),
                    system=prompts.CLUSTER_SYSTEM,
                    response_schema=prompts.CLUSTER_SCHEMA,
                    max_tokens=256,
                )
            )
            verdict = ClusterRelation.model_validate(data)
        except (ProviderError, ValidationError) as exc:
            logger.warning("cluster_confirm_failed", error=str(exc))
            return None

        if verdict.relation == "unrelated":
            return ClusterMatch(
                article=match.article,
                cosine=match.cosine,
                composite=match.composite,
                relation="related",  # keep as related rather than dropping entirely
                confidence=verdict.confidence,
                source="gemini",
            )
        return ClusterMatch(
            article=match.article,
            cosine=match.cosine,
            composite=match.composite,
            relation=verdict.relation,
            confidence=verdict.confidence,
            source="gemini",
        )
