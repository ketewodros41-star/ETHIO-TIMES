"""Velocity window math and breaking-candidate detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.services.intelligence.velocity import (
    compute_snapshots,
    detect_breaking,
    velocity_component_score,
)

from tests.factories import make_article, make_source


def test_compute_snapshots_splits_windows(db_session):
    now = datetime(2026, 9, 9, 18, tzinfo=UTC)
    src = make_source(db_session, slug="vel-src")
    a1 = make_article(db_session, src, title="h1", published_at=now - timedelta(minutes=20))
    a5 = make_article(db_session, src, title="h5", published_at=now - timedelta(hours=5))
    a30 = make_article(db_session, src, title="d2", published_at=now - timedelta(hours=30))
    snaps = compute_snapshots([a1, a5, a30], now=now)
    assert snaps[1].article_count == 1
    assert snaps[6].article_count == 2
    assert snaps[24].article_count == 2
    assert snaps[72].article_count == 3
    assert snaps[1].unique_source_count == 1
    assert snaps[1].articles_per_hour == 1.0


def test_detect_breaking_on_1h_burst(db_session, monkeypatch):
    monkeypatch.setattr(settings, "trend_breaking_min_articles_1h", 3)
    monkeypatch.setattr(settings, "trend_breaking_min_sources_1h", 2)
    now = datetime(2026, 9, 9, 18, tzinfo=UTC)
    a = make_source(db_session, slug="brk-a")
    b = make_source(db_session, slug="brk-b")
    articles = [
        make_article(db_session, a, title="1", published_at=now - timedelta(minutes=10)),
        make_article(db_session, a, title="2", published_at=now - timedelta(minutes=20)),
        make_article(db_session, b, title="3", published_at=now - timedelta(minutes=30)),
    ]
    snaps = compute_snapshots(articles, now=now)
    flag, reasons = detect_breaking(snaps)
    assert flag is True
    assert "burst_1h" in reasons


def test_velocity_component_increases_with_burst():
    quiet = {
        1: VelocitySnapshotLite(0, 0, 0.0),
        6: VelocitySnapshotLite(1, 1, 1.0),
        24: VelocitySnapshotLite(1, 1, 1.0),
    }
    hot = {
        1: VelocitySnapshotLite(4, 3, 4.0),
        6: VelocitySnapshotLite(6, 4, 2.0),
        24: VelocitySnapshotLite(8, 5, 1.5),
    }
    quiet_score, _ = velocity_component_score(_as_snaps(quiet))
    hot_score, _ = velocity_component_score(_as_snaps(hot))
    assert hot_score > quiet_score
    assert hot_score >= 70


class VelocitySnapshotLite:
    def __init__(self, articles: int, sources: int, growth: float) -> None:
        self.article_count = articles
        self.unique_source_count = sources
        self.growth_rate = growth
        self.window_hours = 1
        self.articles_per_hour = float(articles)


def _as_snaps(data: dict) -> dict:
    from app.services.intelligence.velocity import VelocitySnapshot

    out = {}
    for hours, lite in data.items():
        out[hours] = VelocitySnapshot(
            window_hours=hours,
            article_count=lite.article_count,
            unique_source_count=lite.unique_source_count,
            growth_rate=lite.growth_rate,
            articles_per_hour=lite.article_count / hours,
        )
    return out
