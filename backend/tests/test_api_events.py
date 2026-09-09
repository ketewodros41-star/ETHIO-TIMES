"""API filters for event verification status / review_required."""

from __future__ import annotations

from app.api.deps import get_db
from app.main import app
from app.models.enums import EventVerificationStatus, TrendStatus
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
        assert "trend_score" in body
        assert "trend_breakdown" in body
        assert "velocity_metrics" in body
        assert body["trend_status"] == "low"

        a.trend_status = TrendStatus.trending
        a.trend_score = 72
        a.breaking_candidate = False
        b.trend_status = TrendStatus.breaking
        b.trend_score = 91
        b.breaking_candidate = True
        db_session.flush()

        trending = client.get("/api/v1/events", params={"trend_status": "trending"})
        trend_titles = [i["title"] for i in trending.json()["items"]]
        assert "Confirmed coffee harvest" in trend_titles
        assert "Clash requires review" not in trend_titles

        breaking = client.get("/api/v1/events", params={"breaking": True})
        breaking_titles = [i["title"] for i in breaking.json()["items"]]
        assert "Clash requires review" in breaking_titles

        ranked = client.get("/api/v1/events", params={"sort": "trend_score"})
        scores = [i["trend_score"] for i in ranked.json()["items"]]
        assert scores == sorted(scores, reverse=True)
    finally:
        app.dependency_overrides.clear()
