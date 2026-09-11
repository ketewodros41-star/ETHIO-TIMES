"""Smoke test for the API using FastAPI's TestClient.

The health endpoint touches the DB; when no database is reachable it reports a
degraded status rather than raising, so this test asserts the endpoint responds
and returns the expected shape regardless of DB availability.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "ETHIOTIMES"


def test_health_shape():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"status", "service", "database"}
