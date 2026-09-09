"""Sources CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import SourceType
from app.schemas.common import Page, PageMeta
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.services.source_service import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
    SourceService,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=Page[SourceRead])
def list_sources(
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_active: bool | None = Query(None),
    source_type: SourceType | None = Query(None),
    search: str | None = Query(None),
) -> Page[SourceRead]:
    service = SourceService(session)
    items, total = service.list_sources(
        limit=limit,
        offset=offset,
        is_active=is_active,
        source_type=source_type,
        search=search,
    )
    return Page[SourceRead](
        items=[SourceRead.model_validate(i) for i in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate, session: Session = Depends(get_db)
) -> SourceRead:
    service = SourceService(session)
    try:
        source = service.create_source(payload)
    except SourceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with slug '{exc}' already exists",
        ) from exc
    return SourceRead.model_validate(source)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, session: Session = Depends(get_db)) -> SourceRead:
    service = SourceService(session)
    try:
        return SourceRead.model_validate(service.get_source(source_id))
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        ) from exc


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: uuid.UUID, payload: SourceUpdate, session: Session = Depends(get_db)
) -> SourceRead:
    service = SourceService(session)
    try:
        return SourceRead.model_validate(service.update_source(source_id, payload))
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        ) from exc


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_source(source_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    service = SourceService(session)
    try:
        service.delete_source(source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
