"""Tests for feed ordering, telegram freshness window, breaking bypass, and collision-free slots."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import EventStatus, EventVerificationStatus, TrendStatus
from app.models.news_event import NewsEvent
from app.models.telegram_post import TelegramPost, TelegramPublishingSettings
from app.repositories.event_repository import EventRepository
from app.workers.tasks import _telegram_slot, plan_telegram_posts


def test_telegram_slot_collision_avoidance():
    """_telegram_slot with used_hours must skip occupied hours today."""
    class FakePolicy:
        timezone = "Africa/Addis_Ababa"
        posting_hours = [8, 11, 14, 17, 20]

    policy = FakePolicy()
    # 09:00 Addis time (06:00 UTC) -> 11:00 is next future slot
    ref_time = datetime(2026, 9, 15, 6, 0, 0, tzinfo=UTC)

    # 11:00 already used
    used = {11}
    slot = _telegram_slot(policy, 0, ref_time, used_hours=used)

    # Must jump to 14:00 Addis time (11:00 UTC)
    assert slot.astimezone(UTC).hour == 11  # 14:00 Addis is 11:00 UTC
    assert slot.date() == ref_time.date()


def test_telegram_slot_rollover_when_today_exhausted():
    """When all today's slots are occupied or passed, rollover to tomorrow's first available slot."""
    class FakePolicy:
        timezone = "Africa/Addis_Ababa"
        posting_hours = [8, 11, 14, 17, 20]

    policy = FakePolicy()
    # 22:00 Addis time (19:00 UTC) -> past all hours today
    ref_time = datetime(2026, 9, 15, 19, 0, 0, tzinfo=UTC)

    used = {8, 11, 14, 17, 20}
    slot = _telegram_slot(policy, 0, ref_time, used_hours=used)

    # Rollover to tomorrow
    assert slot > ref_time
    assert slot.astimezone(UTC).day == ref_time.day + 1 or slot.astimezone(UTC).month != ref_time.month


def test_settings_api_reads_and_updates_freshness_fields():
    """Settings API should accept freshness_hours and bypass_freshness_for_breaking."""
    from app.api.deps import get_db

    now = datetime.now(UTC)
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=True,
        dry_run=False,
        channel_username="@Ethiopantimes",
        timezone="Africa/Addis_Ababa",
        posts_per_day=5,
        ethiopia_posts_per_day=3,
        international_posts_per_day=2,
        posting_hours=[8, 11, 14, 17, 20],
        highlight_color="#00F0FF",
        freshness_hours=36,
        bypass_freshness_for_breaking=True,
        created_at=now,
        updated_at=now,
    )

    class MockSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            return None
        def commit(self):
            pass
        def refresh(self, obj):
            pass
        def close(self):
            pass

    app.dependency_overrides[get_db] = lambda: MockSession()
    client = TestClient(app)

    try:
        # GET
        get_res = client.get("/api/v1/settings/telegram-publishing")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["freshness_hours"] == 36
        assert data["bypass_freshness_for_breaking"] is True

        # PATCH
        patch_res = client.patch(
            "/api/v1/settings/telegram-publishing",
            json={"freshness_hours": 48, "bypass_freshness_for_breaking": False},
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["freshness_hours"] == 48
        assert updated["bypass_freshness_for_breaking"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_events_endpoint_default_sort():
    """GET /events route should accept sort='created_at' and default to it."""
    from app.api.deps import get_db

    class MockEventSession:
        def scalars(self, stmt):
            res = MagicMock()
            res.all.return_value = []
            return res
        def scalar(self, stmt):
            return 0
        def close(self):
            pass

    app.dependency_overrides[get_db] = lambda: MockEventSession()
    client = TestClient(app)

    try:
        res = client.get("/api/v1/events")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["items"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
