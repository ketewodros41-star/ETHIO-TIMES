"""API filters for event verification status / review_required."""

from __future__ import annotations

from app.api.deps import get_db
from app.main import app
from app.models.enums import EventVerificationStatus
from app.models.news_event import NewsEvent
from fastapi.testclient import TestClient


def test_events_filter_by_verification_and_review(db_session):
    a = NewsEvent(
        title="Confirmed coffee harvest",
        event_verification_status=EventVerificationStatus.confirmed,
        review_required=False,
        verification_score=82,
    )
    b = NewsEvent(
        title="Clash requires review",
        event_verification_status=EventVerificationStatus.contradicted,
        review_required=True,
        verification_score=20,
    )
    db_session.add_all([a, b])
    db_session.flush()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        all_resp = client.get("/api/v1/events")
        assert all_resp.status_code == 200
        assert all_resp.json()["meta"]["total"] >= 2

        confirmed = client.get(
            "/api/v1/events", params={"verification_status": "confirmed"}
        )
        titles = [i["title"] for i in confirmed.json()["items"]]
        assert "Confirmed coffee harvest" in titles
        assert "Clash requires review" not in titles

        review = client.get("/api/v1/events", params={"review_required": True})
        review_titles = [i["title"] for i in review.json()["items"]]
        assert "Clash requires review" in review_titles

        detail = client.get(f"/api/v1/events/{b.id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["event_verification_status"] == "contradicted"
        assert body["review_required"] is True
        assert "claims" in body
        assert "contradictions" in body
        assert body["primary_source_available"] is False
    finally:
        app.dependency_overrides.clear()
