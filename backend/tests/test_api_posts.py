from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from app.api.deps import get_db
from app.main import app
from app.models.enums import EventVerificationStatus, InstagramPostFormat
from app.models.news_event import NewsEvent
from app.models.social_post import SocialPost
from fastapi.testclient import TestClient


def test_list_posts(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "meta" in data
    finally:
        app.dependency_overrides.clear()


def test_get_post_404(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/posts/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_compose_post_endpoint(db_session):
    event = NewsEvent(
        title="Compose Test Event",
        event_verification_status=EventVerificationStatus.confirmed,
        auto_publish_eligible=True,
    )
    db_session.add(event)
    db_session.flush()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        with patch("app.workers.tasks.compose_post.delay") as mock_delay:
            mock_delay.return_value.id = "mock-task-123"
            client = TestClient(app)
            resp = client.post(
                "/api/v1/posts/compose",
                json={
                    "event_id": str(event.id),
                    "format": "portrait",
                    "theme": "verified_brief",
                },
            )
            assert resp.status_code == 202
            assert resp.json()["task_id"] == "mock-task-123"
    finally:
        app.dependency_overrides.clear()


def test_post_eligibility_endpoint(db_session):
    event = NewsEvent(
        title="Contradicted Event",
        event_verification_status=EventVerificationStatus.contradicted,
        auto_publish_eligible=False,
        review_required=True,
        primary_category="politics",
    )
    db_session.add(event)
    db_session.flush()

    post = SocialPost(
        event_id=event.id,
        theme="verified_brief",
        headline="Test Headline",
        caption="Test Caption",
        format=InstagramPostFormat.portrait,
    )
    db_session.add(post)
    db_session.flush()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/posts/{post.id}/eligibility")
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligible"] is False
        assert "review_required" in data["blocked_reasons"]
        assert "contradicted" in data["blocked_reasons"]
    finally:
        app.dependency_overrides.clear()

