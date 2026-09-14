"""Unit and integration tests for Telegram publishing automation."""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.integrations.publishers.telegram import TelegramPublisher
from app.main import app
from app.models.news_event import NewsEvent
from app.models.telegram_post import TelegramPost, TelegramPublishingSettings
from app.services.social.translation_service import EditorialTranslationService
from app.workers.tasks import _telegram_slot, plan_telegram_posts, publish_due_telegram_posts


# =====================================================================
# 1. TelegramPublisher Tests
# =====================================================================

def test_telegram_publisher_dry_run_without_bot_token():
    """Dry-run publishing should succeed even when TELEGRAM_BOT_TOKEN is not configured."""
    publisher = TelegramPublisher()
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Test Headline",
        description="Test Description",
        caption="Test Caption",
        source_attribution="ETHIOPIAN TIMES",
        dry_run=True,
    )
    with patch.object(settings, "telegram_bot_token", None):
        assert not publisher.is_configured()
        result = publisher.publish(post, "@Ethiopantimes")
        assert result.error is None
        assert result.message_id == f"dry-run-{post.id}"
        assert result.published_at is not None


def test_telegram_publisher_live_mode_without_token_fails():
    """Live publishing without token must fail cleanly with descriptive error."""
    publisher = TelegramPublisher()
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Test Headline",
        description="Test Description",
        caption="Test Caption",
        source_attribution="ETHIOPIAN TIMES",
        dry_run=False,
    )
    with patch.object(settings, "telegram_bot_token", None):
        result = publisher.publish(post, "@Ethiopantimes")
        assert result.message_id is None
        assert "not configured" in (result.error or "")


def test_telegram_caption_truncation_preserves_html_tags_and_limit():
    """Caption truncation must not slice across HTML tags and must never exceed 1024 chars."""
    long_text = "Word " * 300  # ~1500 chars
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="A" * 300,
        description=long_text,
        caption="C" * 200,
        source_attribution="S" * 100,
        photo_credit="P" * 100,
        highlight_words=["Key1", "Key2", "Key3", "IgnoredKey4"],
        dry_run=True,
    )
    caption = TelegramPublisher._caption(post)
    assert len(caption) <= 1024

    # Validate that tags are well-formed and balanced
    assert caption.count("<b>") == caption.count("</b>")
    assert caption.count("<i>") == caption.count("</i>")
    assert not re.search(r"<[^>]*$", caption), "Found unclosed HTML tag at end of caption"


def test_telegram_caption_escapes_special_characters_cleanly():
    """HTML special characters in headline/description/source must be escaped properly."""
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="international",
        language="en",
        headline="Breaking: Leaders & Ministers Meet <Today> in 'Addis' \"Peace\" Talks",
        description="Economics & Finance -> Growth exceeds > 5% & inflation < 10% in Q1.",
        caption="Follow @Ethiopantimes & stay updated.",
        source_attribution="Reuters & ENA",
        photo_credit="Photographer & Co",
        highlight_words=["Finance & Growth", "Addis <Peace>"],
        dry_run=True,
    )
    caption = TelegramPublisher._caption(post)
    assert "<Today>" not in caption
    assert "&lt;Today&gt;" in caption
    assert "Finance &amp; Growth" in caption
    assert caption.count("<b>") == caption.count("</b>")
    assert caption.count("<i>") == caption.count("</i>")
    assert len(caption) <= 1024


# =====================================================================
# 2. Slot Calculation Tests
# =====================================================================

def test_telegram_slot_distribution_and_overflow():
    """_telegram_slot must index into configured hours and stagger overflow ordinals."""
    class FakePolicy:
        timezone = "Africa/Addis_Ababa"
        posting_hours = [8, 11, 14, 17, 20]

    policy = FakePolicy()
    ref_time = datetime(2026, 9, 12, 2, 0, 0, tzinfo=UTC)

    slot_0 = _telegram_slot(policy, 0, ref_time)
    slot_1 = _telegram_slot(policy, 1, ref_time)
    slot_2 = _telegram_slot(policy, 2, ref_time)
    slot_4 = _telegram_slot(policy, 4, ref_time)
    slot_5 = _telegram_slot(policy, 5, ref_time)

    # Slot 0 should be 08:00 Addis = 05:00 UTC
    assert slot_0 == datetime(2026, 9, 12, 5, 0, 0, tzinfo=UTC)
    # Slot 1 should be 11:00 Addis = 08:00 UTC
    assert slot_1 == datetime(2026, 9, 12, 8, 0, 0, tzinfo=UTC)
    # Slot 2 should be 14:00 Addis = 11:00 UTC
    assert slot_2 == datetime(2026, 9, 12, 11, 0, 0, tzinfo=UTC)
    # Slot 4 should be 20:00 Addis = 17:00 UTC
    assert slot_4 == datetime(2026, 9, 12, 17, 0, 0, tzinfo=UTC)
    # Slot 5 should be 20:30 Addis = 17:30 UTC (staggered past 20:00)
    assert slot_5 == datetime(2026, 9, 12, 17, 30, 0, tzinfo=UTC)
    assert slot_5 > slot_4


# =====================================================================
# 3. Settings API Routes Tests
# =====================================================================

def test_settings_telegram_api_auto_balance_and_validation():
    """PATCH /settings/telegram-publishing auto-balances quotas and enforces constraints."""
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
        created_at=now,
        updated_at=now,
    )

    class MockSettingsSession:
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

    app.dependency_overrides[get_db] = lambda: MockSettingsSession()
    client = TestClient(app)

    try:
        # 1. Read settings
        resp = client.get("/api/v1/settings/telegram-publishing")
        assert resp.status_code == 200
        original_data = resp.json()
        assert "posts_per_day" in original_data
        assert "ethiopia_posts_per_day" in original_data
        assert "international_posts_per_day" in original_data

        # 2. Update total posts_per_day only -> should auto-balance ethiopia (60%) and international (40%)
        patch_resp = client.patch(
            "/api/v1/settings/telegram-publishing",
            json={"posts_per_day": 10},
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["posts_per_day"] == 10
        assert updated["ethiopia_posts_per_day"] == 6
        assert updated["international_posts_per_day"] == 4

        # 3. Update regional breakdown only -> should auto-sum total posts_per_day
        patch_resp2 = client.patch(
            "/api/v1/settings/telegram-publishing",
            json={"ethiopia_posts_per_day": 5, "international_posts_per_day": 2},
        )
        assert patch_resp2.status_code == 200
        updated2 = patch_resp2.json()
        assert updated2["posts_per_day"] == 7
        assert updated2["ethiopia_posts_per_day"] == 5
        assert updated2["international_posts_per_day"] == 2

        # 4. Mismatched explicit quotas must be rejected with 422
        err_resp = client.patch(
            "/api/v1/settings/telegram-publishing",
            json={
                "posts_per_day": 10,
                "ethiopia_posts_per_day": 4,
                "international_posts_per_day": 4,
            },
        )
        assert err_resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# 4. Translation Service Context Loading Tests
# =====================================================================

def test_translation_service_event_context_uses_get_detail():
    """_event_context must call event_repo.get_detail and extract verified claims."""
    mock_session = MagicMock()
    mock_event_repo = MagicMock()
    test_event_id = uuid.uuid4()

    mock_claim_1 = MagicMock()
    mock_claim_1.claim_text = "Verified claim text 1"
    mock_claim_1.evidence = [MagicMock()]

    mock_claim_no_evidence = MagicMock()
    mock_claim_no_evidence.claim_text = "Unverified claim"
    mock_claim_no_evidence.evidence = []

    mock_event = MagicMock()
    mock_event.id = test_event_id
    mock_event.claims = [mock_claim_1, mock_claim_no_evidence]

    mock_event_repo.get_detail.return_value = mock_event

    service = EditorialTranslationService(mock_session, MagicMock())
    service.event_repo = mock_event_repo

    # Test with string UUID
    event, facts = service._event_context(str(test_event_id))
    assert event == mock_event
    assert facts == ["Verified claim text 1"]
    mock_event_repo.get_detail.assert_called_with(test_event_id)

    # Test with UUID object
    event2, facts2 = service._event_context(test_event_id)
    assert event2 == mock_event
    assert facts2 == ["Verified claim text 1"]


# =====================================================================
# 5. Publish Due Telegram Posts Worker Task
# =====================================================================

def test_publish_due_telegram_posts_dry_run():
    """publish_due_telegram_posts should find scheduled posts and deliver/simulate them."""
    now = datetime.now(UTC)
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=True,
        dry_run=True,
        channel_username="@Ethiopantimes",
        timezone="Africa/Addis_Ababa",
        posting_hours=[8, 11, 14, 17, 20],
        highlight_color="#00F0FF",
        created_at=now,
        updated_at=now,
    )
    test_post_id = uuid.uuid4()
    test_post = TelegramPost(
        id=test_post_id,
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Test Scheduled Due Post",
        description="Short description",
        caption="Test Caption",
        source_attribution="ETHIOPIAN TIMES",
        status="scheduled",
        scheduled_at=datetime.now(UTC) - timedelta(minutes=5),
        dry_run=True,
    )

    class MockPublishSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            if model is TelegramPost and ident == test_post_id:
                return test_post
            return None
        def scalars(self, stmt):
            mock_res = MagicMock()
            mock_res.all.return_value = [test_post]
            return mock_res
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockPublishSession):
        res = publish_due_telegram_posts()
        assert res["published"] >= 1
        assert test_post.status == "simulated"
        assert test_post.published_at is not None
        assert test_post.telegram_message_id == f"dry-run-{test_post_id}"


# =====================================================================
# 6. Plan Telegram Posts Task Quota Respect Tests
# =====================================================================

def test_plan_telegram_posts_disabled():
    """plan_telegram_posts must return 0 planned when policy.enabled is False."""
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=False,
        channel_username="@Ethiopantimes",
        timezone="Africa/Addis_Ababa",
    )
    class MockDisabledSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            return None
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockDisabledSession):
        res = plan_telegram_posts()
        assert res["planned"] == 0
        assert res["reason"] == "telegram_automation_disabled"


# =====================================================================
# 7. Channel Normalization & Dynamic Policy Tests
# =====================================================================

def test_telegram_publisher_normalizes_channel_username():
    """TelegramPublisher must automatically prefix channel username with @ if missing."""
    publisher = TelegramPublisher()
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Test Channel Normalization",
        description="Description",
        caption="Caption",
        source_attribution="ETHIOPIAN TIMES",
        dry_run=False,
    )
    with patch("httpx.post") as mock_post, patch.object(settings, "telegram_bot_token", "fake-token"):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 9999}}
        mock_post.return_value = mock_resp

        res = publisher.publish(post, "CustomChannel")
        assert res.error is None
        assert res.message_id == "9999"

        call_args = mock_post.call_args
        assert call_args[1]["data"]["chat_id"] == "@CustomChannel"


def test_publish_due_telegram_posts_respects_policy_dry_run_override():
    """When policy.dry_run=True, even posts scheduled with dry_run=False must be simulated."""
    now = datetime.now(UTC)
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=True,
        dry_run=True,
        channel_username="@Ethiopantimes",
        timezone="Africa/Addis_Ababa",
        posting_hours=[8, 11, 14, 17, 20],
        highlight_color="#00F0FF",
        created_at=now,
        updated_at=now,
    )
    test_post_id = uuid.uuid4()
    test_post = TelegramPost(
        id=test_post_id,
        event_id=uuid.uuid4(),
        content_bucket="international",
        language="en",
        headline="Test Scheduled Post With Live Flag",
        description="Description",
        caption="Caption",
        source_attribution="ETHIOPIAN TIMES",
        status="scheduled",
        scheduled_at=datetime.now(UTC) - timedelta(minutes=10),
        dry_run=False,  # originally scheduled as live
    )

    class MockOverrideSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            if model is TelegramPost and ident == test_post_id:
                return test_post
            return None
        def scalars(self, stmt):
            mock_res = MagicMock()
            mock_res.all.return_value = [test_post]
            return mock_res
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockOverrideSession):
        res = publish_due_telegram_posts()
        assert res["published"] >= 1
        assert res["dry_run"] is True
        assert test_post.status == "simulated"
        assert test_post.dry_run is True
        assert test_post.telegram_message_id == f"dry-run-{test_post_id}"


def test_telegram_slot_spacing_catch_up():
    """When scheduled slot is already in the past, slots are spaced 15 minutes apart."""
    class FakePolicy:
        timezone = "Africa/Addis_Ababa"
        posting_hours = [8, 11, 14, 17, 20]

    policy = FakePolicy()
    # 22:00 Addis time (19:00 UTC) -> all posting hours are in the past
    now = datetime(2026, 9, 12, 19, 0, 0, tzinfo=UTC)

    slot_0 = _telegram_slot(policy, 0, now)
    slot_1 = _telegram_slot(policy, 1, now)
    slot_2 = _telegram_slot(policy, 2, now)

    diff_0_1 = (slot_1 - slot_0).total_seconds() / 60
    diff_1_2 = (slot_2 - slot_1).total_seconds() / 60

    assert diff_0_1 == 15.0
    assert diff_1_2 == 15.0


def test_telegram_regional_classification_query():
    """Regional classification must correctly match Ethiopian cities/regions and non-Ethiopian items in an isolated in-memory DB."""
    from sqlalchemy import Boolean, Column, String, and_, create_engine, not_, or_, select
    from sqlalchemy.orm import declarative_base, sessionmaker

    TestBase = declarative_base()

    class TestNewsEvent(TestBase):
        __tablename__ = "test_news_events_classification"
        id = Column(String, primary_key=True)
        title = Column(String, nullable=False)
        summary = Column(String, nullable=True)
        primary_region = Column(String, nullable=True)
        primary_category = Column(String, nullable=True)
        auto_publish_eligible = Column(Boolean, default=True)
        review_required = Column(Boolean, default=False)

    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    try:
        ethiopia_region_terms = (
            "ethiop", "addis", "amhara", "tigray", "oromia", "somali", "afar",
            "benishangul", "gambella", "harar", "sidama", "dire dawa",
            "southern nations", "south west", "raya", "wollega", "axum", "mekelle"
        )
        eth_region_cond = or_(*(TestNewsEvent.primary_region.ilike(f"%{t}%") for t in ethiopia_region_terms))
        eth_title_cond = or_(*(TestNewsEvent.title.ilike(f"%{t}%") for t in ("%ethiop%", "%addis%", "%amhara%", "%tigray%", "%oromia%")))
        is_ethiopia_expr = or_(eth_region_cond, eth_title_cond)
        is_intl_expr = or_(
            TestNewsEvent.primary_category.in_([
                "World", "World News", "International News", "International Relations", "world", "world news"
            ]),
            and_(TestNewsEvent.primary_region.is_(None), not_(eth_title_cond)),
            and_(not_(eth_region_cond), not_(eth_title_cond)),
        )

        ev_addis = TestNewsEvent(
            id="ev-addis",
            title="Addis Ababa infrastructure project launches",
            summary="New roads in Addis",
            primary_region="Addis Ababa",
            auto_publish_eligible=True,
            review_required=False,
        )
        ev_intl = TestNewsEvent(
            id="ev-intl",
            title="French parliament debates energy reform",
            summary="New law voted in Paris",
            primary_region=None,
            primary_category="World News",
            auto_publish_eligible=True,
            review_required=False,
        )
        session.add_all([ev_addis, ev_intl])
        session.commit()

        # Check ev_addis matches is_ethiopia_expr
        matched_eth = list(session.scalars(select(TestNewsEvent).where(TestNewsEvent.id == ev_addis.id, is_ethiopia_expr)).all())
        assert len(matched_eth) == 1

        # Check ev_intl matches is_intl_expr
        matched_intl = list(session.scalars(select(TestNewsEvent).where(TestNewsEvent.id == ev_intl.id, is_intl_expr)).all())
        assert len(matched_intl) == 1
    finally:
        session.close()
        engine.dispose()


# =====================================================================
# 9. Test-Post / Immediate Live Broadcast Endpoint Tests
# =====================================================================

def test_telegram_test_post_endpoint_without_token():
    """POST /settings/telegram-publishing/test-post returns 400 when bot token is not configured."""
    client = TestClient(app)
    with patch.object(settings, "telegram_bot_token", None):
        resp = client.post("/api/v1/settings/telegram-publishing/test-post", json={})
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]


def test_telegram_test_post_endpoint_success_dispatch():
    """POST /settings/telegram-publishing/test-post dispatches immediately with dry_run=False."""
    from app.api.deps import get_db
    from app.integrations.publishers.telegram import TelegramPublishResult
    client = TestClient(app)

    now = datetime.now(UTC)
    dynamic_msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=True,
        dry_run=False,
        channel_username="@TestChannel",
        timezone="Africa/Addis_Ababa",
        posts_per_day=5,
        ethiopia_posts_per_day=3,
        international_posts_per_day=2,
        posting_hours=[8, 11, 14, 17, 20],
        highlight_color="#00F0FF",
        created_at=now,
        updated_at=now,
    )
    mock_event = NewsEvent(
        id=uuid.uuid4(),
        title="Addis Ababa infrastructure expansion announced",
        summary="Major progress reported",
        primary_region="Addis Ababa",
        auto_publish_eligible=True,
        review_required=False,
        created_at=now,
        last_seen_at=now,
    )

    class MockTestPostSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            if model is NewsEvent:
                return mock_event
            return None
        def scalars(self, stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "from articles" in stmt_str:
                mock_res.first.return_value = None
            elif "from telegram_posts" in stmt_str:
                mock_res.first.return_value = None
                mock_res.all.return_value = []
            else:
                mock_res.first.return_value = mock_event
                mock_res.all.return_value = [mock_event]
            return mock_res
        def add(self, obj):
            pass
        def commit(self):
            pass
        def refresh(self, obj):
            pass
        def delete(self, obj):
            pass
        def close(self):
            pass

    app.dependency_overrides[get_db] = lambda: MockTestPostSession()
    try:
        with patch.object(settings, "telegram_bot_token", "dummy-token"), \
             patch.object(TelegramPublisher, "publish") as mock_publish:
            mock_publish.return_value = TelegramPublishResult(dynamic_msg_id, datetime.now(UTC), None)

            resp = client.post(
                "/api/v1/settings/telegram-publishing/test-post",
                json={"channel_username": "@TestChannel"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["telegram_message_id"] == dynamic_msg_id
            assert data["channel"] == "@TestChannel"
            assert data["status"] == "published"
            assert mock_publish.called
            # Check dry_run was False
            args, kwargs = mock_publish.call_args
            assert kwargs.get("dry_run") is False
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# 10. Photo Resolution & Multipart Guarantee Tests
# =====================================================================

def test_telegram_publisher_resolve_image_bytes_fallbacks():
    """Verify _resolve_image_bytes reliably supplies valid bytes for all scenarios."""
    publisher = TelegramPublisher()

    # 1. No photo provided (Ethiopia bucket)
    p_none_eth = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Ethiopia News",
        photo_url=None,
    )
    b_eth, fn_eth = publisher._resolve_image_bytes(p_none_eth)
    assert len(b_eth) >= 5000
    assert fn_eth == "ethiopia.jpg"

    # 2. Ephemeral telesco.pe URL (must be intercepted and replaced with fallback)
    p_tg = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Tikvah Report",
        photo_url="https://cdn4.telesco.pe/file/expired123.jpg",
    )
    b_tg, fn_tg = publisher._resolve_image_bytes(p_tg)
    assert len(b_tg) >= 5000
    assert fn_tg == "ethiopia.jpg"

    # 3. International bucket with 404 URL
    p_intl = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="international",
        language="en",
        headline="Global News",
        photo_url="https://httpbin.org/status/404",
    )
    b_intl, fn_intl = publisher._resolve_image_bytes(p_intl)
    assert len(b_intl) >= 5000
    assert fn_intl == "international.jpg"


def test_telegram_publisher_multipart_send_photo(monkeypatch):
    """Verify publish sends photo as multipart byte payload and never falls back to sendMessage."""
    publisher = TelegramPublisher()
    post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Live Broadcast",
        description="News content",
        photo_url=None,
        dry_run=False,
    )

    captured_requests = []

    def mock_post(url, *args, **kwargs):
        captured_requests.append((url, kwargs))
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 9999}}
        return mock_resp

    monkeypatch.setattr("httpx.post", mock_post)

    with patch.object(settings, "telegram_bot_token", "fake-token-123"):
        result = publisher.publish(post, "@Ethiopantimes")
        assert result.error is None
        assert result.message_id == "9999"

        # Verify sendPhoto was called with multipart files payload
        assert len(captured_requests) == 1
        call_url, call_kwargs = captured_requests[0]
        assert call_url.endswith("/sendPhoto")
        assert "files" in call_kwargs
        assert "photo" in call_kwargs["files"]
        filename, photo_bytes, mime = call_kwargs["files"]["photo"]
        assert filename == "ethiopia.jpg"
        assert len(photo_bytes) >= 5000
        assert mime == "image/jpeg"


# =====================================================================
# 11. Quota Discounting & Live Mode Isolation Tests
# =====================================================================

def test_plan_telegram_posts_quota_discounts_simulated_and_test_in_live_mode():
    """In live mode (dry_run=False), simulated posts and test dispatches do not consume quota."""
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
        created_at=now,
        updated_at=now,
    )

    # 3 simulated posts + 1 test dispatch post today
    sim_posts = [
        TelegramPost(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            content_bucket="ethiopia",
            language="am",
            headline=f"Simulated Post {i}",
            description="Desc",
            caption="Caption",
            source_attribution="ETHIOPIAN TIMES",
            status="simulated",
            scheduled_at=now - timedelta(hours=i + 1),
            published_at=now - timedelta(hours=i + 1),
            telegram_message_id=f"dry-run-{uuid.uuid4()}",
            dry_run=True,
        )
        for i in range(3)
    ]
    test_dispatch_post = TelegramPost(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        content_bucket="ethiopia",
        language="am",
        headline="Test Dispatch Post",
        description="Desc",
        caption="Caption",
        source_attribution="ETHIOPIAN TIMES",
        status="published",
        scheduled_at=now - timedelta(minutes=30),
        published_at=now - timedelta(minutes=30),
        telegram_message_id="msg-abcdef12",
        dry_run=False,
        policy_snapshot={"test_dispatch": True},
    )

    fake_event = NewsEvent(
        id=uuid.uuid4(),
        title="Addis Ababa major new development announced today",
        summary="Summary of progress",
        primary_region="Addis Ababa",
        primary_category="News",
        auto_publish_eligible=True,
        review_required=False,
        created_at=now,
        last_seen_at=now,
    )

    class MockPlanSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            if model is NewsEvent:
                return fake_event
            return None
        def scalars(self, stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "telegram_posts.scheduled_at >=" in stmt_str:
                # today_posts
                mock_res.all.return_value = sim_posts + [test_dispatch_post]
            elif "news_events" in stmt_str:
                mock_res.all.return_value = [fake_event]
            elif "telegram_posts.event_id" in stmt_str:
                # already_event_ids query
                mock_res.all.return_value = []
            elif "telegram_posts" in stmt_str:
                mock_res.first.return_value = None
            else:
                mock_res.all.return_value = []
            return mock_res
        def add(self, obj):
            pass
        def commit(self):
            pass
        def flush(self):
            pass
        def refresh(self, obj):
            pass
        def delete(self, obj):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockPlanSession), \
         patch("app.services.social.translation_service.EditorialTranslationService") as mock_trans, \
         patch("app.services.social.image_pipeline.ImagePipeline") as mock_img:
        mock_trans.return_value.translate_editorial.return_value = MagicMock(
            headline="የአዲስ አበባ አዲስ ልማት", dek="ማጠቃለያ", punchline_words=[]
        )
        mock_img.return_value.browse_photos.return_value = MagicMock(items=[])

        res = plan_telegram_posts()
        # In live mode, because simulated and test posts were discounted,
        # quota is NOT full, so the new event was planned!
        assert res["planned"] >= 1


def test_plan_telegram_posts_quota_counts_simulated_in_dry_run_mode():
    """In dry-run mode (dry_run=True), simulated posts count against dry run quota."""
    now = datetime.now(UTC)
    mock_policy = TelegramPublishingSettings(
        id=1,
        enabled=True,
        dry_run=True,
        channel_username="@Ethiopantimes",
        timezone="Africa/Addis_Ababa",
        posts_per_day=3,
        ethiopia_posts_per_day=3,
        international_posts_per_day=0,
        posting_hours=[8, 11, 14],
        highlight_color="#00F0FF",
        created_at=now,
        updated_at=now,
    )

    sim_posts = [
        TelegramPost(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            content_bucket="ethiopia",
            language="am",
            headline=f"Simulated Post {i}",
            description="Desc",
            caption="Caption",
            source_attribution="ETHIOPIAN TIMES",
            status="simulated",
            scheduled_at=now - timedelta(hours=i + 1),
            published_at=now - timedelta(hours=i + 1),
            telegram_message_id=f"dry-run-{uuid.uuid4()}",
            dry_run=True,
        )
        for i in range(3)
    ]

    class MockDryRunSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            return None
        def scalars(self, stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "telegram_posts.scheduled_at >=" in stmt_str:
                mock_res.all.return_value = sim_posts
            else:
                mock_res.all.return_value = []
            return mock_res
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockDryRunSession):
        res = plan_telegram_posts()
        # Quota is 3, 3 simulated posts exist, so in dry run mode 0 should be planned
        assert res["planned"] == 0


def test_already_event_ids_query_retains_scheduled_posts_with_null_message_id():
    """Verify that SQL query for already_event_ids does not drop scheduled posts with telegram_message_id=None."""
    from sqlalchemy import Boolean, Column, String, and_, create_engine, or_, select
    from sqlalchemy.orm import declarative_base, sessionmaker

    TestBase = declarative_base()

    class TestPostModel(TestBase):
        __tablename__ = "test_post_null_id"
        id = Column(String, primary_key=True)
        event_id = Column(String, nullable=False)
        status = Column(String, nullable=False)
        dry_run = Column(Boolean, default=False)
        telegram_message_id = Column(String, nullable=True)

    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    try:
        ev_scheduled_id = "event-scheduled-1"
        ev_published_live_id = "event-published-live"
        ev_test_id = "event-test-dummy"
        ev_simulated_id = "event-dry-run-sim"

        session.add_all([
            # 1. Scheduled post (telegram_message_id is None) -> MUST be in already_event_ids
            TestPostModel(id="1", event_id=ev_scheduled_id, status="scheduled", dry_run=False, telegram_message_id=None),
            # 2. Published live post -> MUST be in already_event_ids
            TestPostModel(id="2", event_id=ev_published_live_id, status="published", dry_run=False, telegram_message_id="12345"),
            # 3. Test post msg-xxx -> MUST NOT be in already_event_ids
            TestPostModel(id="3", event_id=ev_test_id, status="published", dry_run=False, telegram_message_id="msg-abc"),
            # 4. Dry-run post -> MUST NOT be in already_event_ids in live mode
            TestPostModel(id="4", event_id=ev_simulated_id, status="simulated", dry_run=True, telegram_message_id="dry-run-xyz"),
        ])
        session.commit()

        # Query matching tasks.py live mode
        stmt = select(TestPostModel.event_id).where(
            TestPostModel.status.in_(["scheduled", "publishing", "published"]),
            TestPostModel.dry_run.is_(False),
            or_(
                TestPostModel.telegram_message_id.is_(None),
                and_(
                    ~TestPostModel.telegram_message_id.ilike("msg-%"),
                    ~TestPostModel.telegram_message_id.ilike("dry-run-%"),
                ),
            ),
        )
        matched_event_ids = set(session.scalars(stmt).all())
        assert ev_scheduled_id in matched_event_ids, "Scheduled post with None message_id was incorrectly excluded!"
        assert ev_published_live_id in matched_event_ids
        assert ev_test_id not in matched_event_ids
        assert ev_simulated_id not in matched_event_ids
    finally:
        session.close()
        engine.dispose()


def test_plan_telegram_posts_translation_failure_graceful_fallback():
    """When translation service fails on an English article, plan_telegram_posts falls back to English headline rather than dropping the post."""
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
        created_at=now,
        updated_at=now,
    )

    fake_english_event = NewsEvent(
        id=uuid.uuid4(),
        title="Ethiopia signs major renewable energy pact in Addis Ababa",
        summary="Clean energy initiative expands national grid capacity.",
        primary_region="Addis Ababa",
        primary_category="Energy",
        auto_publish_eligible=True,
        review_required=False,
        created_at=now,
        last_seen_at=now,
    )

    class MockFallbackSession:
        def get(self, model, ident):
            if model is TelegramPublishingSettings:
                return mock_policy
            if model is NewsEvent:
                return fake_english_event
            return None
        def scalars(self, stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "telegram_posts.scheduled_at >=" in stmt_str:
                mock_res.all.return_value = []
            elif "news_events" in stmt_str:
                mock_res.all.return_value = [fake_english_event]
            elif "telegram_posts.event_id" in stmt_str:
                mock_res.all.return_value = []
            elif "telegram_posts" in stmt_str:
                mock_res.first.return_value = None
            else:
                mock_res.all.return_value = []
            return mock_res
        def add(self, obj):
            pass
        def commit(self):
            pass
        def flush(self):
            pass
        def refresh(self, obj):
            pass
        def delete(self, obj):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    with patch("app.workers.tasks.SessionLocal", side_effect=MockFallbackSession), \
         patch("app.services.social.translation_service.EditorialTranslationService") as mock_trans, \
         patch("app.services.social.image_pipeline.ImagePipeline") as mock_img:
        # Simulate AI translation failure (e.g. invalid API key or timeout)
        mock_trans.return_value.translate_editorial.side_effect = RuntimeError("API key invalid (401)")
        mock_img.return_value.browse_photos.return_value = MagicMock(items=[])

        res = plan_telegram_posts()
        # Even though translation failed, fallback allows post to be planned!
        assert res["planned"] >= 1





