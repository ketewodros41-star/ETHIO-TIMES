"""Tests for Ingestion stop and cancellation endpoint and service logic."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from app.main import app
from app.models.enums import JobStatus
from app.services.ingestion_service import IngestionService
from fastapi.testclient import TestClient

client = TestClient(app)


def test_stop_ingest_specific_source():
    source_id = str(uuid.uuid4())
    resp = client.post("/api/v1/ingest/stop", json={"source_id": source_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["stopped"] is True
    assert data["source_id"] == source_id
    assert "stopped for source" in data["message"].lower()


def test_stop_ingest_all_sources():
    resp = client.post("/api/v1/ingest/stop", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["stopped"] is True
    assert data["source_id"] is None
    assert "all active ingestions stopped" in data["message"].lower()


def test_ingestion_service_cancels_before_start():
    mock_session = MagicMock()
    service = IngestionService(mock_session)
    source_id = uuid.uuid4()

    # When cancel_check returns True immediately
    res = service.ingest_source(source_id, cancel_check=lambda: True)
    assert res.status == JobStatus.skipped
    assert "stopped by user" in res.error.lower()
