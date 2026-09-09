"""Business logic for managing news sources."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import SourceType
from app.models.news_source import NewsSource
from app.repositories.source_repository import SourceRepository
from app.schemas.source import SourceCreate, SourceUpdate


class SourceAlreadyExistsError(Exception):
    pass


class SourceNotFoundError(Exception):
    pass


class SourceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SourceRepository(session)

    def list_sources(
        self,
        *,
        limit: int,
        offset: int,
        is_active: bool | None,
        source_type: SourceType | None,
        search: str | None,
    ) -> tuple[list[NewsSource], int]:
        return self.repo.list(
            limit=limit,
            offset=offset,
            is_active=is_active,
            source_type=source_type,
            search=search,
        )

    def get_source(self, source_id: uuid.UUID) -> NewsSource:
        source = self.repo.get(source_id)
        if source is None:
            raise SourceNotFoundError(str(source_id))
        return source

    def create_source(self, payload: SourceCreate) -> NewsSource:
        import re

        data = payload.model_dump()
        slug = payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")
        data["slug"] = slug
        if self.repo.get_by_slug(slug) is not None:
            raise SourceAlreadyExistsError(slug)
        source = NewsSource(**data)
        try:
            self.repo.create(source)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SourceAlreadyExistsError(slug) from exc
        self.session.refresh(source)
        return source

    def update_source(self, source_id: uuid.UUID, payload: SourceUpdate) -> NewsSource:
        source = self.get_source(source_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(source, field, value)
        self.session.commit()
        self.session.refresh(source)
        return source

    def delete_source(self, source_id: uuid.UUID) -> None:
        source = self.get_source(source_id)
        self.repo.delete(source)
        self.session.commit()

    def list_health(self) -> list[NewsSource]:
        items, _ = self.repo.list(limit=1000, offset=0)
        return items
