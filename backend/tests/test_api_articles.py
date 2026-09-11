"Tests for article endpoints, ensure-event, and event linking."

from __future__ import annotations

import uuid
from app.api.deps import get_db
from app.main import app
from app.models.article import Article
from app.models.news_source import NewsSource
from app.models.enums import SourceType
from fastapi.testclient import TestClient


def test_ensure_article_event_and_event_id(db_session):
    source = NewsSource(
        name="Test Sports Wire",
        slug="test-sports-wire-" + uuid.uuid4().hex[:6],
        source_type=SourceType.rss,
        country="Ethiopia",
        language="en",
    )
    db_session.add(source)
    db_session.flush()

    article = Article(
        source_id=source.id,
        canonical_url="https://example.com/sports/" + uuid.uuid4().hex[:8],
        title="Mbappé arrives in Addis for charity friendly",
        summary="French star Kylian Mbappé visits Addis Ababa stadium.",
        categories=["Sports", "Football"],
        importance_score=85.0,
    )
    db_session.add(article)
    db_session.commit()

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)

        # 1. Initial article detail before event creation
        res1 = client.get(f"/api/v1/articles/{article.id}")
        assert res1.status_code == 200
        assert res1.json()["event_id"] is None

        # 2. Call ensure-event to provision event
        res2 = client.post(f"/api/v1/articles/{article.id}/ensure-event")
        assert res2.status_code == 200
        event_data = res2.json()
        assert event_data["title"] == "Mbappé arrives in Addis for charity friendly"
        assert event_data["primary_category"] == "Sports"
        assert "Sports" in event_data["categories"]
        assert event_data["article_count"] == 1
        event_id = event_data["id"]

        # 3. Article detail now returns event_id
        res3 = client.get(f"/api/v1/articles/{article.id}")
        assert res3.status_code == 200
        assert res3.json()["event_id"] == event_id

        # 4. Calling ensure-event again is idempotent and returns the same event
        res4 = client.post(f"/api/v1/articles/{article.id}/ensure-event")
        assert res4.status_code == 200
        assert res4.json()["id"] == event_id

        # 5. Non-existent article returns 404
        bad_id = uuid.uuid4()
        res5 = client.post(f"/api/v1/articles/{bad_id}/ensure-event")
        assert res5.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
