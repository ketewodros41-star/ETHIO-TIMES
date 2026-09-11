"""Publish service with eligibility gates (Phase 5, spec §§21, 41)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.publishers.base import BasePublisher, PublishResult
from app.models.enums import EventVerificationStatus, SocialPostStatus
from app.models.social_post import SocialPost
from app.repositories.social_post_repository import SocialPostRepository
from app.services.social.render_service import RenderService

_SENSITIVE_CATEGORIES = {
    "politics", "conflict", "military", "deaths", "crime",
    "ethnic", "religion", "elections", "safety",
    "financial_panic", "disasters",
}

logger = get_logger(__name__)

class PublishBlockedError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"publish_blocked: {reason}")

class PublishService:
    def __init__(
        self,
        session: Session,
        publisher: BasePublisher,
        render_service: RenderService,
    ) -> None:
        self.session = session
        self.publisher = publisher
        self.render_service = render_service
        self.post_repo = SocialPostRepository(session)

    def publish(self, post: SocialPost) -> PublishResult:
        event = post.event
        self._check_gates(post, event)
        if not post.media_path:
            media_path = self.render_service.render_post(post)
            self.post_repo.update_media(post.id, str(media_path), None)
        else:
            media_path = Path(post.media_path)
            
        result = self.publisher.publish(post, media_path)
        self.post_repo.update_publish_result(
            post.id,
            ig_media_id=result.ig_media_id,
            ig_post_id=result.platform_post_id,
            published_at=result.published_at,
        )
        self.post_repo.update_status(post.id, SocialPostStatus.published)
        return result

    def _check_gates(self, post: SocialPost, event) -> None:
        if event.review_required:
            raise PublishBlockedError("review_required")
        if event.event_verification_status == EventVerificationStatus.contradicted:
            raise PublishBlockedError("contradicted")
        if not event.auto_publish_eligible:
            raise PublishBlockedError("not_eligible")
        cat = (event.primary_category or "").lower()
        if cat in _SENSITIVE_CATEGORIES:
            raise PublishBlockedError(f"sensitive_category:{cat}")

    def check_eligibility(self, post: SocialPost) -> tuple[bool, list[str]]:
        reasons = []
        event = post.event
        if event.review_required:
            reasons.append("review_required")
        if event.event_verification_status == EventVerificationStatus.contradicted:
            reasons.append("contradicted")
        if not event.auto_publish_eligible:
            reasons.append("not_eligible")
        cat = (event.primary_category or "").lower()
        if cat in _SENSITIVE_CATEGORIES:
            reasons.append(f"sensitive_category:{cat}")
        return len(reasons) == 0, reasons
