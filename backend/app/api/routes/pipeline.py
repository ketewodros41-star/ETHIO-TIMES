"""Pipeline observability endpoints (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.article import Article
from app.models.enums import (
    EventVerificationStatus,
    EventVerifyStatus,
    ProcessingStatus,
    TrendStatus,
)
from app.models.news_event import NewsEvent

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
