"""Schemas for ingestion trigger / job tracking."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus


class IngestTriggerRequest(BaseModel):
    source_id: uuid.UUID | None = None  # None => enqueue all active sources


class IngestTriggerResponse(BaseModel):
    enqueued: bool
    task_id: str | None = None
    source_ids: list[uuid.UUID]
    message: str


class PipelineJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_name: str
    celery_task_id: str | None = None
    source_id: uuid.UUID | None = None
    status: JobStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    items_processed: int
    items_created: int
    error_message: str | None = None
    created_at: datetime
