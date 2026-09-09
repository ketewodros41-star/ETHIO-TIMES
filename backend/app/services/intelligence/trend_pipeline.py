"""Trend intelligence orchestrator (Phase 4).

Recomputes velocity metrics, editorial importance, Gemini trend signals (with
heuristic fallback on call failure), and the weighted ``trend_score``. Idempotent:
a fresh score is skipped unless new coverage arrived or the caller passes
``force``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider
from app.models.article import Article
from app.models.enums import TrendStatus
from app.models.news_event import EventArticle, NewsEvent
from app.models.verification import EventClaim
from app.services.intelligence.importance import score_editorial_importance
from app.services.intelligence.trend_scoring import (
    assess_trend_signals,
    combine_trend_score,
)
from app.services.intelligence.velocity import (
    compute_snapshots,
    detect_breaking,
    persist_snapshots,
    velocity_component_score,
)

logger = get_logger(__name__)


@dataclass
class TrendPipelineResult:
    event_id: str
    skipped: bool = False
    score: float | None = None
    status: TrendStatus | None = None
    breaking_candidate: bool = False
    error: str | None = None
    steps_run: list[str] = field(default_factory=list)
    gemini_fallback: bool = False

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "skipped": self.skipped,
            "score": self.score,
            "status": self.status.value if self.status else None,
            "breaking_candidate": self.breaking_candidate,
            "error": self.error,
            "steps_run": self.steps_run,
            "gemini_fallback": self.gemini_fallback,
        }


class TrendPipeline:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider

    def process(self, event: NewsEvent, *, force: bool = False) -> TrendPipelineResult:
        result = TrendPipelineResult(
            event_id=str(event.id),
            score=event.trend_score,
            status=event.trend_status,
            breaking_candidate=event.breaking_candidate,
        )
        if self._should_skip(event, force=force):
            result.skipped = True
            return result

        now = datetime.now(UTC)
        try:
            articles = self._load_articles(event.id)
            claims = self._load_claims(event.id)
            result.steps_run.append("load")

            snapshots = compute_snapshots(articles, now=now)
            persist_snapshots(self.session, event.id, snapshots, now=now)
            velocity, velocity_detail = velocity_component_score(snapshots)
            heuristic_breaking, breaking_reasons = detect_breaking(snapshots)
            result.steps_run.append("velocity")

            editorial, editorial_detail = score_editorial_importance(
                event, articles, claims
            )
            result.steps_run.append("importance")

            signals, used_fallback = assess_trend_signals(
                self.provider, event, articles
            )
            result.gemini_fallback = used_fallback
            result.steps_run.append("signals_fallback" if used_fallback else "signals")

            scored = combine_trend_score(
                event=event,
                articles=articles,
                snapshots=snapshots,
                velocity=velocity,
                velocity_detail=velocity_detail,
                editorial_importance=editorial,
                editorial_detail=editorial_detail,
                signals=signals,
                used_gemini_fallback=used_fallback,
                heuristic_breaking_reasons=breaking_reasons if heuristic_breaking else [],
                now=now,
            )
            result.steps_run.append("score")

            event.trend_score = scored.score
            event.trend_status = scored.status
            event.trend_breakdown = scored.breakdown
            event.editorial_importance = editorial
            event.breaking_candidate = scored.breaking_candidate
            event.trend_scored_at = now
            # Keep the clustering significance_score in lockstep so older
            # surfaces that still sort on it see trend-aware ordering.
            event.significance_score = scored.score
            self.session.flush()

            result.score = scored.score
            result.status = scored.status
            result.breaking_candidate = scored.breaking_candidate
            logger.info(
                "event_trend_scored",
                event_id=result.event_id,
                score=scored.score,
                status=scored.status.value,
                breaking=scored.breaking_candidate,
                gemini_fallback=used_fallback,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "trend_scoring_failed", event_id=result.event_id, error=result.error
            )
            return result

    def _should_skip(self, event: NewsEvent, *, force: bool) -> bool:
        if force:
            return False
        if event.trend_scored_at is None:
            return False
        if event.last_seen_at and event.last_seen_at > event.trend_scored_at:
            return False
        fresh = timedelta(seconds=settings.trend_skip_fresh_seconds)
        scored_at = event.trend_scored_at
        if scored_at.tzinfo is None:
            scored_at = scored_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - scored_at < fresh

    def _load_articles(self, event_id) -> list[Article]:  # noqa: ANN001
        stmt = (
            select(Article)
            .join(EventArticle, EventArticle.article_id == Article.id)
            .where(EventArticle.event_id == event_id)
            .options(selectinload(Article.source), selectinload(Article.analysis))
        )
        return list(self.session.scalars(stmt).all())

    def _load_claims(self, event_id) -> list[EventClaim]:  # noqa: ANN001
        return list(
            self.session.scalars(
                select(EventClaim).where(EventClaim.event_id == event_id)
            ).all()
        )
