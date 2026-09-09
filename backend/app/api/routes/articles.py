"""Article list/detail endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import ArticleStatus
from app.schemas.article import ArticleDetail, ArticleRead
from app.schemas.common import Page, PageMeta
from app.services.article_service import ArticleNotFoundError, ArticleService

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=Page[ArticleRead])
def list_articles(
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_id: uuid.UUID | None = Query(None),
    status_filter: ArticleStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
) -> Page[ArticleRead]:
    service = ArticleService(session)
    items, total = service.list_articles(
        limit=limit,
        offset=offset,
        source_id=source_id,
        status=status_filter,
        search=search,
    )
    return Page[ArticleRead](
        items=[ArticleRead.model_validate(i) for i in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{article_id}", response_model=ArticleDetail)
def get_article(article_id: uuid.UUID, session: Session = Depends(get_db)) -> ArticleDetail:
    service = ArticleService(session)
    try:
        return ArticleDetail.model_validate(service.get_article(article_id))
    except ArticleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Article not found"
        ) from exc
