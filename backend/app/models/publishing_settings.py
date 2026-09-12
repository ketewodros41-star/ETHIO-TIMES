"""Single-operator publishing automation policy."""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PublishingSettings(Base, TimestampMixin):
    __tablename__ = "publishing_settings"

    # A true singleton avoids ambiguous global policy. Row 1 is created lazily.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    posts_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    automation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Addis_Ababa", server_default="Africa/Addis_Ababa")
