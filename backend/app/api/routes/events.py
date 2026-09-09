"""News event feed + detail endpoints (Phase 2)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import EventStatus
from app.repositories.event_repository import EventRepository
from app.schemas.common import Page, PageMeta
from app.schemas.event import EventDetail, EventRead, to_event_detail

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=Page[EventRead])
def list_events(
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: EventStatus | None = Query(None, alias="status"),
    category: str | None = Query(None),
    search: str | None = Query(None),
) -> Page[EventRead]:
    repo = EventRepository(session)
    items, total = repo.list(
        limit=limit,
        offset=offset,
        status=status_filter,
        category=category,
        search=search,
    )
    return Page[EventRead](
        items=[EventRead.model_validate(e) for e in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: uuid.UUID, session: Session = Depends(get_db)) -> EventDetail:
    repo = EventRepository(session)
    event = repo.get_detail(event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return to_event_detail(event)
