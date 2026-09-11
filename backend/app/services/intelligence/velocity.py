"""Event coverage velocity (Phase 4).

Computes per-window article/source counts and growth rates, persists
``event_velocity_metrics``, and flags ``breaking_candidate`` bursts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.article import Article
from app.models.trending import VELOCITY_WINDOWS_HOURS, EventVelocityMetric

_GROWTH_FLOOR = 0.5


@dataclass
class VelocitySnapshot:
    window_hours: int
    article_count: int
    unique_source_count: int
    growth_rate: float
    articles_per_hour: float
    previous_article_count: int = 0
    extra: dict = field(default_factory=dict)


def article_timestamp(article: Article) -> datetime | None:
    """Best available coverage timestamp (publication preferred)."""
    ts = article.published_at or article.fetched_at or article.created_at
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def compute_snapshots(
    articles: list[Article],
    *,
    now: datetime | None = None,
    windows: tuple[int, ...] = VELOCITY_WINDOWS_HOURS,
) -> dict[int, VelocitySnapshot]:
    """Pure velocity math — no DB writes."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    timed: list[tuple[datetime, Article]] = []
    for article in articles:
        ts = article_timestamp(article)
        if ts is not None:
            timed.append((ts, article))

    snapshots: dict[int, VelocitySnapshot] = {}
    for hours in windows:
        cutoff = now - timedelta(hours=hours)
        prev_cutoff = now - timedelta(hours=hours * 2)
        current = [a for ts, a in timed if ts >= cutoff]
        previous = [a for ts, a in timed if prev_cutoff <= ts < cutoff]
        article_count = len(current)
        sources = {a.source_id for a in current}
        prev_count = len(previous)
        growth = article_count / max(prev_count, _GROWTH_FLOOR)
        snapshots[hours] = VelocitySnapshot(
            window_hours=hours,
            article_count=article_count,
            unique_source_count=len(sources),
            growth_rate=round(growth, 3),
            articles_per_hour=round(article_count / hours, 3),
            previous_article_count=prev_count,
            extra={
                "previous_article_count": prev_count,
                "previous_source_count": len({a.source_id for a in previous}),
            },
        )
    return snapshots


def detect_breaking(
    snapshots: dict[int, VelocitySnapshot],
) -> tuple[bool, list[str]]:
    """Rapid-growth heuristic. Gemini may add a second signal later."""
    reasons: list[str] = []
    w1 = snapshots.get(1)
    w6 = snapshots.get(6)
    if (
        w1
        and w1.article_count >= settings.trend_breaking_min_articles_1h
        and w1.unique_source_count >= settings.trend_breaking_min_sources_1h
    ):
        reasons.append("burst_1h")
    if (
        w1
        and w6
        and w1.growth_rate >= settings.trend_breaking_min_growth
        and w6.article_count >= 3
    ):
        reasons.append("growth_spike")
    if w6 and w6.article_count >= 8 and w6.unique_source_count >= 3:
        reasons.append("sustained_6h")
    return bool(reasons), reasons


def persist_snapshots(
    session: Session,
    event_id,
    snapshots: dict[int, VelocitySnapshot],
    *,
    now: datetime | None = None,
) -> list[EventVelocityMetric]:
    """Upsert one row per window for the event."""
    now = now or datetime.now(UTC)
    existing = {
        row.window_hours: row
        for row in session.scalars(
            select(EventVelocityMetric).where(EventVelocityMetric.event_id == event_id)
        ).all()
    }
    rows: list[EventVelocityMetric] = []
    for hours, snap in snapshots.items():
        row = existing.get(hours)
        if row is None:
            row = EventVelocityMetric(event_id=event_id, window_hours=hours)
            session.add(row)
        row.article_count = snap.article_count
        row.unique_source_count = snap.unique_source_count
        row.growth_rate = snap.growth_rate
        row.articles_per_hour = snap.articles_per_hour
        row.computed_at = now
        row.extra = snap.extra
        rows.append(row)
    session.flush()
    return rows


def velocity_component_score(snapshots: dict[int, VelocitySnapshot]) -> tuple[float, dict]:
    """Map 1h/6h snapshots onto a 0–100 velocity component."""
    w1 = snapshots.get(1)
    w6 = snapshots.get(6)
    w24 = snapshots.get(24)
    articles_1h = w1.article_count if w1 else 0
    sources_1h = w1.unique_source_count if w1 else 0
    articles_6h = w6.article_count if w6 else 0
    sources_6h = w6.unique_source_count if w6 else 0
    growth = w1.growth_rate if w1 else 0.0

    article_burst = min(100.0, articles_1h * 28.0 + articles_6h * 8.0)
    source_burst = min(100.0, sources_1h * 32.0 + sources_6h * 10.0)
    growth_score = min(100.0, growth * 28.0)
    sustained = min(100.0, (w24.article_count if w24 else 0) * 5.0)
    score = 0.40 * article_burst + 0.30 * source_burst + 0.20 * growth_score + 0.10 * sustained
    score = max(0.0, min(100.0, round(score, 1)))
    detail = {
        "articles_1h": articles_1h,
        "sources_1h": sources_1h,
        "articles_6h": articles_6h,
        "sources_6h": sources_6h,
        "growth_rate_1h": round(growth, 3),
        "article_burst": round(article_burst, 1),
        "source_burst": round(source_burst, 1),
        "growth_score": round(growth_score, 1),
        "sustained_24h": round(sustained, 1),
    }
    return score, detail
