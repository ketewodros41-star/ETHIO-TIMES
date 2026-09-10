"""Pipeline observability endpoints (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.article import Article
from app.models.audit import PipelineJob
from app.models.enums import (
    EventVerificationStatus,
    EventVerifyStatus,
    ProcessingStatus,
    TrendStatus,
)
from app.models.news_event import EventArticle, NewsEvent

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/stats")
def pipeline_stats(session: Session = Depends(get_db)) -> dict:
    """Counts by processing status plus embedding/analysis/event coverage."""
    status_counts = {s.value: 0 for s in ProcessingStatus}
    rows = session.execute(
        select(Article.processing_status, func.count())
        .group_by(Article.processing_status)
    ).all()
    for status_value, count in rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        status_counts[key] = count

    total_articles = session.scalar(select(func.count()).select_from(Article)) or 0
    embedded = (
        session.scalar(
            select(func.count()).select_from(Article).where(Article.embedding.isnot(None))
        )
        or 0
    )
    relevant = (
        session.scalar(
            select(func.count())
            .select_from(Article)
            .where(Article.is_ethiopia_related.is_(True))
        )
        or 0
    )
    total_events = session.scalar(select(func.count()).select_from(NewsEvent)) or 0

    verify_counts = {s.value: 0 for s in EventVerifyStatus}
    v_rows = session.execute(
        select(NewsEvent.verification_processing_status, func.count()).group_by(
            NewsEvent.verification_processing_status
        )
    ).all()
    for status_value, count in v_rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        verify_counts[key] = count

    public_counts = {s.value: 0 for s in EventVerificationStatus}
    p_rows = session.execute(
        select(NewsEvent.event_verification_status, func.count()).group_by(
            NewsEvent.event_verification_status
        )
    ).all()
    for status_value, count in p_rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        public_counts[key] = count

    review_required = (
        session.scalar(
            select(func.count())
            .select_from(NewsEvent)
            .where(NewsEvent.review_required.is_(True))
        )
        or 0
    )

    trend_counts = {s.value: 0 for s in TrendStatus}
    t_rows = session.execute(
        select(NewsEvent.trend_status, func.count()).group_by(NewsEvent.trend_status)
    ).all()
    for status_value, count in t_rows:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        trend_counts[key] = count

    breaking = (
        session.scalar(
            select(func.count())
            .select_from(NewsEvent)
            .where(NewsEvent.breaking_candidate.is_(True))
        )
        or 0
    )

    return {
        "total_articles": total_articles,
        "embedded": embedded,
        "ethiopia_related": relevant,
        "total_events": total_events,
        "by_processing_status": status_counts,
        "by_event_verify_status": verify_counts,
        "by_event_verification_status": public_counts,
        "review_required_events": review_required,
        "by_trend_status": trend_counts,
        "breaking_candidates": breaking,
    }


@router.post("/prune-stale")
def prune_stale_storage(
    session: Session = Depends(get_db),
    jobs_max_age_days: int = 7,
    articles_max_age_days: int = 60,
) -> dict:
    """Supabase Free Tier storage maintenance:
    - Prunes completed/failed pipeline_jobs older than jobs_max_age_days.
    - Prunes unlinked stale articles older than articles_max_age_days with no associated event.
    """
    cutoff_jobs = datetime.now(UTC) - timedelta(days=jobs_max_age_days)
    stmt_jobs = delete(PipelineJob).where(PipelineJob.created_at < cutoff_jobs)
    res_jobs = session.execute(stmt_jobs)
    deleted_jobs = res_jobs.rowcount or 0

    cutoff_articles = datetime.now(UTC) - timedelta(days=articles_max_age_days)
    subq = (
        select(1)
        .select_from(EventArticle)
        .where(EventArticle.article_id == Article.id)
    )
    stmt_articles = delete(Article).where(
        Article.created_at < cutoff_articles,
        ~subq.exists(),
    )
    res_articles = session.execute(stmt_articles)
    deleted_articles = res_articles.rowcount or 0

    session.commit()
    return {
        "deleted_jobs": deleted_jobs,
        "deleted_articles": deleted_articles,
        "message": f"Successfully cleaned up {deleted_jobs} old job logs and {deleted_articles} stale unlinked articles.",
    }

