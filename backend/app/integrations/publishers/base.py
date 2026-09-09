"""Publisher interface (spec §39).

All social platform publishers implement BasePublisher.
InstagramPublisher is the Phase 5 implementation.
TelegramPublisher, XPublisher etc. are Phase 6+.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models.social_post import SocialPost

@dataclass
class PublishResult:
    platform_post_id: str | None
    ig_media_id: str | None
    dry_run: bool
    published_at: datetime | None
    error: str | None = None

class BasePublisher(ABC):
    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def publish(self, post: SocialPost, image_path: Path) -> PublishResult: ...
