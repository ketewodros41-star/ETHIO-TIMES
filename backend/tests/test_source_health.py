"""Source health bookkeeping should represent recovery accurately."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import SourceHealthStatus
from app.repositories.source_repository import SourceRepository


def test_success_clears_a_previous_error_and_records_content_time():
    source = SimpleNamespace(
        last_checked_at=None,
        last_success_at=None,
        last_content_at=None,
        last_error_at=object(),
        last_error_message="old 403",
        consecutive_failures=2,
        health_status=SourceHealthStatus.degraded,
        total_articles_ingested=4,
    )

    SourceRepository(None).mark_success(source, ingested_count=3, fetched_count=8)

    assert source.health_status is SourceHealthStatus.healthy
    assert source.consecutive_failures == 0
    assert source.last_error_at is None
    assert source.last_error_message is None
    assert source.last_content_at is not None
    assert source.total_articles_ingested == 7
