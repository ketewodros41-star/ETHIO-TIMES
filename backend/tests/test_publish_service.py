from __future__ import annotations

import pytest
from app.integrations.publishers.instagram import InstagramPublisher
from app.models.enums import EventVerificationStatus
from app.models.news_event import NewsEvent
from app.models.social_post import SocialPost
from app.services.social.publish_service import PublishBlockedError, PublishService
from app.services.social.render_service import RenderService


def test_publish_blocked_review_required():
    event = NewsEvent(
        title="Event 1",
        review_required=True,
        event_verification_status=EventVerificationStatus.confirmed,
        auto_publish_eligible=True,
        primary_category="general",
    )
    post = SocialPost(event=event)
    svc = PublishService(None, InstagramPublisher(), RenderService())

    with pytest.raises(PublishBlockedError, match="review_required"):
        svc._check_gates(post, event)


def test_publish_blocked_contradicted():
    event = NewsEvent(
        title="Event 2",
        review_required=False,
        event_verification_status=EventVerificationStatus.contradicted,
        auto_publish_eligible=True,
        primary_category="general",
    )
    post = SocialPost(event=event)
    svc = PublishService(None, InstagramPublisher(), RenderService())

    with pytest.raises(PublishBlockedError, match="contradicted"):
        svc._check_gates(post, event)


def test_publish_blocked_not_eligible():
    event = NewsEvent(
        title="Event 3",
        review_required=False,
        event_verification_status=EventVerificationStatus.confirmed,
        auto_publish_eligible=False,
        primary_category="general",
    )
    post = SocialPost(event=event)
    svc = PublishService(None, InstagramPublisher(), RenderService())

    with pytest.raises(PublishBlockedError, match="not_eligible"):
        svc._check_gates(post, event)


def test_publish_blocked_sensitive_category():
    event = NewsEvent(
        title="Event 4",
        review_required=False,
        event_verification_status=EventVerificationStatus.confirmed,
        auto_publish_eligible=True,
        primary_category="politics",
    )
    post = SocialPost(event=event)
    svc = PublishService(None, InstagramPublisher(), RenderService())

    with pytest.raises(PublishBlockedError, match="sensitive_category:politics"):
        svc._check_gates(post, event)


def test_check_eligibility():
    event = NewsEvent(
        title="Event 5",
        review_required=True,
        event_verification_status=EventVerificationStatus.contradicted,
        auto_publish_eligible=False,
        primary_category="military",
    )
    post = SocialPost(event=event)
    svc = PublishService(None, InstagramPublisher(), RenderService())

    eligible, reasons = svc.check_eligibility(post)
    assert not eligible
    assert "review_required" in reasons
    assert "contradicted" in reasons
    assert "not_eligible" in reasons
    assert "sensitive_category:military" in reasons
