"""Instagram Graph API publisher (Phase 5)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.publishers.base import BasePublisher, PublishResult
from app.models.social_post import SocialPost

logger = get_logger(__name__)

class InstagramPublisher(BasePublisher):
    def is_configured(self) -> bool:
        return bool(settings.instagram_access_token and settings.instagram_business_account_id)

    def publish(self, post: SocialPost, image_path: Path) -> PublishResult:
        if not self.is_configured():
            logger.info("ig_publish_dry_run", post_id=str(post.id))
            return PublishResult(
                platform_post_id=f"dry-run-{post.id}",
                ig_media_id=f"dry-run-container-{post.id}",
                dry_run=True,
                published_at=datetime.now(UTC),
            )
        # Real publish logic would go here
        return PublishResult(
            platform_post_id=f"ig-{post.id}",
            ig_media_id=f"ig-media-{post.id}",
            dry_run=False,
            published_at=datetime.now(UTC),
        )
