"""Intelligence pipeline orchestrator (Phase 2).

Runs the per-article stages in order:

    (collected/normalized) -> relevance -> analysis -> embedding -> cluster

Each stage is **idempotent** (guarded by the article's persisted state), so a
re-run resumes where it left off. Irrelevant articles short-circuit after the
relevance stage. Embedding + clustering require the AI provider; when it is
unavailable the pipeline stops after analysis (the beat poller only advances
those stages when a provider is configured).

Failures increment ``processing_attempts``; once attempts reach
``pipeline_max_attempts`` the article moves to the ``dead_letter`` state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderNotConfiguredError
from app.models.article import Article, ArticleAnalysis
from app.models.enums import ProcessingStatus, RelevanceDecision
from app.services.intelligence.analysis_service import AnalysisService
from app.services.intelligence.clustering_service import ClusteringService
from app.services.intelligence.embedding_service import EmbeddingService
from app.services.intelligence.event_service import EventService
from app.services.intelligence.relevance_service import RelevanceService

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    article_id: str
    final_status: ProcessingStatus
    steps_run: list[str] = field(default_factory=list)
    error: str | None = None
    event_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "final_status": self.final_status.value,
            "steps_run": self.steps_run,
            "error": self.error,
            "event_id": self.event_id,
        }


class IntelligencePipeline:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.relevance = RelevanceService(provider)
        self.analysis = AnalysisService(provider)
        self.embedding = EmbeddingService(provider)
        self.clustering = ClusteringService(session, provider)
        self.events = EventService(session)

    def process(self, article: Article) -> PipelineResult:
        result = PipelineResult(
            article_id=str(article.id), final_status=article.processing_status
        )
        try:
            if article.processing_status in (
                ProcessingStatus.pending,
                ProcessingStatus.failed,
            ) and article.relevance_scored_at is None:
                self._step_relevance(article, result)
                if article.processing_status == ProcessingStatus.skipped_irrelevant:
                    result.final_status = article.processing_status
                    return result

            if article.analysis is None:
                self._step_analysis(article, result)

            if article.embedding is None:
                if not self.provider.is_available():
                    # Cannot embed/cluster without a provider; stop after analysis.
                    result.final_status = article.processing_status
                    return result
                self._step_embedding(article, result)

            if (
                article.embedding is not None
                and article.processing_status != ProcessingStatus.clustered
            ):
                self._step_cluster(article, result)

            article.processing_error = None
            result.final_status = article.processing_status
            return result

        except Exception as exc:  # noqa: BLE001 - record and classify failure
            self.session.rollback()
            # Re-fetch since rollback expired the instance.
            fresh = self.session.get(Article, article.id)
            if fresh is not None:
                fresh.processing_attempts += 1
                fresh.processing_error = f"{type(exc).__name__}: {exc}"[:2000]
                if fresh.processing_attempts >= settings.pipeline_max_attempts:
                    fresh.processing_status = ProcessingStatus.dead_letter
                else:
                    fresh.processing_status = ProcessingStatus.failed
                result.final_status = fresh.processing_status
            result.error = f"{type(exc).__name__}: {exc}"
            logger.warning("pipeline_step_failed", article_id=result.article_id, error=result.error)
            return result

    # -- steps -------------------------------------------------------------- #
    def _step_relevance(self, article: Article, result: PipelineResult) -> None:
        outcome = self.relevance.assess(
            title=article.title, summary=article.summary, content=article.content
        )
        r = outcome.result
        article.relevance_score = r.score
        article.relevance_decision = outcome.decision
        article.is_ethiopia_related = r.is_ethiopia_related
        article.relevance_reason = r.reason
        article.primary_region = r.primary_region
        article.ethiopia_relevance_score = r.score / 100.0
        article.relevance_scored_at = datetime.now(UTC)
        result.steps_run.append("relevance")
        if outcome.decision == RelevanceDecision.irrelevant:
            article.processing_status = ProcessingStatus.skipped_irrelevant
        else:
            article.processing_status = ProcessingStatus.relevance_scored
        self.session.flush()

    def _step_analysis(self, article: Article, result: PipelineResult) -> None:
        analysis, _fallback = self.analysis.analyze(
            title=article.title, summary=article.summary, content=article.content
        )
        record = ArticleAnalysis(
            article_id=article.id,
            language=analysis.language,
            language_name=analysis.language_name,
            category=analysis.category,
            subcategory=analysis.subcategory,
            importance=analysis.importance,
            summary=analysis.summary,
            entities=analysis.entities.model_dump(),
            entity_names=analysis.entities.all_names(),
            topics=analysis.topics,
            dates=[d.model_dump() for d in analysis.dates],
            money=[m.model_dump() for m in analysis.money],
            statistics=[s.model_dump() for s in analysis.statistics],
            model=self.provider.name if self.provider.is_available() else "fallback",
        )
        self.session.add(record)
        article.analysis = record
        article.detected_language = analysis.language
        article.importance_score = float(analysis.importance)
        article.analyzed_at = datetime.now(UTC)
        article.processing_status = ProcessingStatus.analyzed
        result.steps_run.append("analysis")
        self.session.flush()

    def _step_embedding(self, article: Article, result: PipelineResult) -> None:
        try:
            ok = self.embedding.embed_article(article)
        except ProviderNotConfiguredError:
            return
        if ok:
            article.processing_status = ProcessingStatus.embedded
            result.steps_run.append("embedding")
            self.session.flush()

    def _step_cluster(self, article: Article, result: PipelineResult) -> None:
        match = self.clustering.find_best_match(article)
        event = self.events.assign(article, match)
        article.processing_status = ProcessingStatus.clustered
        result.event_id = str(event.id)
        result.steps_run.append("cluster")
        self.session.flush()
