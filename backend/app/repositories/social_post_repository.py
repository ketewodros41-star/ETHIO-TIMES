from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SocialPlatform, SocialPostStatus
from app.models.social_post import SocialPost

class SocialPostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, post: SocialPost) -> SocialPost:
        self.session.add(post)
        self.session.flush()
        return post

    def get(self, post_id: uuid.UUID) -> SocialPost | None:
        return self.session.get(SocialPost, post_id)
        
    def get_with_event(self, post_id: uuid.UUID) -> SocialPost | None:
        return self.session.scalar(
            select(SocialPost).options(selectinload(SocialPost.event)).where(SocialPost.id == post_id)
        )

    def list(
        self,
        *,
        limit: int,
        offset: int,
        status: SocialPostStatus | None = None,
        platform: SocialPlatform | None = None,
        event_id: uuid.UUID | None = None,
        theme: str | None = None,
    ) -> tuple[Sequence[SocialPost], int]:
        stmt = select(SocialPost)
        if status:
            stmt = stmt.where(SocialPost.status == status)
        if platform:
            stmt = stmt.where(SocialPost.platform == platform)
        if event_id:
            stmt = stmt.where(SocialPost.event_id == event_id)
        if theme:
            stmt = stmt.where(SocialPost.theme == theme)
            
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        
        stmt = stmt.order_by(SocialPost.created_at.desc()).limit(limit).offset(offset)
        items = self.session.scalars(stmt).all()
        return items, total

    def update_status(self, post_id: uuid.UUID, status: SocialPostStatus, error: str | None = None) -> None:
        post = self.get(post_id)
        if post:
            post.status = status
            if error is not None:
                post.error = error
            self.session.add(post)

    def update_media(self, post_id: uuid.UUID, media_path: str, media_url: str | None = None) -> None:
        post = self.get(post_id)
        if post:
            post.media_path = media_path
            if media_url:
                post.media_url = media_url
            self.session.add(post)

    def update_publish_result(
        self, post_id: uuid.UUID, ig_media_id: str | None, ig_post_id: str | None, published_at
    ) -> None:
        post = self.get(post_id)
        if post:
            if ig_media_id:
                post.ig_media_id = ig_media_id
            if ig_post_id:
                post.ig_post_id = ig_post_id
            if published_at:
                post.published_at = published_at
            self.session.add(post)

    def get_for_event(self, event_id: uuid.UUID) -> Sequence[SocialPost]:
        return self.session.scalars(select(SocialPost).where(SocialPost.event_id == event_id)).all()

    def has_post_for_event(self, event_id: uuid.UUID) -> bool:
        stmt = select(func.count(SocialPost.id)).where(SocialPost.event_id == event_id)
        count = self.session.scalar(stmt) or 0
        return count > 0
