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
    client = TestClient(app)

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

    # 5. Restore original settings
    restore_resp = client.patch(
        "/api/v1/settings/telegram-publishing",
        json={
            "posts_per_day": original_data["posts_per_day"],
            "ethiopia_posts_per_day": original_data["ethiopia_posts_per_day"],
            "international_posts_per_day": original_data["international_posts_per_day"],
        },
    )
    assert restore_resp.status_code == 200


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
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        policy = session.get(TelegramPublishingSettings, 1)
        if policy is None:
            policy = TelegramPublishingSettings(id=1, enabled=True, dry_run=True)
            session.add(policy)
        else:
            policy.enabled = True
            policy.dry_run = True

        event = session.query(NewsEvent).first()
        if not event:
            event = NewsEvent(
                title="Test Event For Telegram",
                summary="Test Summary",
                auto_publish_eligible=True,
                review_required=False,
            )
            session.add(event)
            session.flush()

        test_post = TelegramPost(
            event_id=event.id,
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
        session.add(test_post)
        session.commit()
        test_post_id = test_post.id

        res = publish_due_telegram_posts()
        assert res["published"] >= 1

        refreshed_session = SessionLocal()
        try:
            delivered_post = refreshed_session.get(TelegramPost, test_post_id)
            assert delivered_post is not None
            assert delivered_post.status == "simulated"
            assert delivered_post.published_at is not None
            assert delivered_post.telegram_message_id == f"dry-run-{test_post_id}"
        finally:
            p = refreshed_session.get(TelegramPost, test_post_id)
            if p:
                refreshed_session.delete(p)
                refreshed_session.commit()
            refreshed_session.close()

    finally:
        session.close()


# =====================================================================
# 6. Plan Telegram Posts Task Quota Respect Tests
# =====================================================================

def test_plan_telegram_posts_disabled():
    """plan_telegram_posts must return 0 planned when policy.enabled is False."""
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        policy = session.get(TelegramPublishingSettings, 1)
        if policy is None:
            policy = TelegramPublishingSettings(id=1, enabled=False)
            session.add(policy)
        else:
            policy.enabled = False
        session.commit()

        res = plan_telegram_posts()
        assert res["planned"] == 0
        assert res["reason"] == "telegram_automation_disabled"
    finally:
        # Re-enable
        policy = session.get(TelegramPublishingSettings, 1)
        if policy:
            policy.enabled = True
            session.commit()
        session.close()


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
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        policy = session.get(TelegramPublishingSettings, 1)
        if policy is None:
            policy = TelegramPublishingSettings(id=1, enabled=True, dry_run=True)
            session.add(policy)
        else:
            policy.enabled = True
            policy.dry_run = True

        event = session.query(NewsEvent).first()
        if not event:
            event = NewsEvent(
                title="Test Event For Dry Run Override",
                summary="Test Summary",
                auto_publish_eligible=True,
                review_required=False,
            )
            session.add(event)
            session.flush()

        test_post = TelegramPost(
            event_id=event.id,
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
        session.add(test_post)
        session.commit()
        test_post_id = test_post.id

        res = publish_due_telegram_posts()
        assert res["published"] >= 1
        assert res["dry_run"] is True

        refreshed_session = SessionLocal()
        try:
            delivered_post = refreshed_session.get(TelegramPost, test_post_id)
            assert delivered_post is not None
            assert delivered_post.status == "simulated"
            assert delivered_post.dry_run is True
            assert delivered_post.telegram_message_id == f"dry-run-{test_post_id}"
        finally:
            p = refreshed_session.get(TelegramPost, test_post_id)
            if p:
                refreshed_session.delete(p)
                refreshed_session.commit()
            refreshed_session.close()
    finally:
        session.close()


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
    """Regional classification must correctly match Ethiopian cities/regions and non-Ethiopian items."""
    from sqlalchemy import and_, not_, or_, select
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        ethiopia_region_terms = (
            "ethiop", "addis", "amhara", "tigray", "oromia", "somali", "afar",
            "benishangul", "gambella", "harar", "sidama", "dire dawa",
            "southern nations", "south west", "raya", "wollega", "axum", "mekelle"
        )
        eth_region_cond = or_(*(NewsEvent.primary_region.ilike(f"%{t}%") for t in ethiopia_region_terms))
        eth_title_cond = or_(*(NewsEvent.title.ilike(f"%{t}%") for t in ("%ethiop%", "%addis%", "%amhara%", "%tigray%", "%oromia%")))
        is_ethiopia_expr = or_(eth_region_cond, eth_title_cond)
        is_intl_expr = or_(
            NewsEvent.primary_category.in_([
                "World", "World News", "International News", "International Relations", "world", "world news"
            ]),
            and_(NewsEvent.primary_region.is_(None), not_(eth_title_cond)),
            and_(not_(eth_region_cond), not_(eth_title_cond)),
        )

        ev_addis = NewsEvent(
            title="Addis Ababa infrastructure project launches",
            summary="New roads in Addis",
            primary_region="Addis Ababa",
            auto_publish_eligible=True,
            review_required=False,
        )
        ev_intl = NewsEvent(
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
        matched_eth = list(session.scalars(select(NewsEvent).where(NewsEvent.id == ev_addis.id, is_ethiopia_expr)).all())
        assert len(matched_eth) == 1

        # Check ev_intl matches is_intl_expr
        matched_intl = list(session.scalars(select(NewsEvent).where(NewsEvent.id == ev_intl.id, is_intl_expr)).all())
        assert len(matched_intl) == 1

        # Cleanup
        session.delete(ev_addis)
        session.delete(ev_intl)
        session.commit()
    finally:
        session.close()


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
    from app.integrations.publishers.telegram import TelegramPublishResult
    client = TestClient(app)

    dynamic_msg_id = f"msg-{uuid.uuid4().hex[:8]}"
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



