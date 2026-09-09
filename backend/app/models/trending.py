"""`event_velocity_metrics` — per-window coverage velocity for trend scoring."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.news_event import NewsEvent

# Canonical windows used by the trend pipeline (hours).
VELOCITY_WINDOWS_HOURS: tuple[int, ...] = (1, 6, 24, 72)


class EventVelocityMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Coverage velocity for one event over one lookback window.

    ``growth_rate`` is current-window article count divided by the previous
    equal-length window (floored at a small epsilon so brand-new events do not
    explode to infinity).
    """

    __tablename__ = "event_velocity_metrics"
    __table_args__ = (
        UniqueConstraint("event_id", "window_hours", name="uq_event_velocity_window"),
        {"comment": "Per-window article/source velocity snapshots for news events."},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    article_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    unique_source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    growth_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    articles_per_hour: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extra: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    event: Mapped[NewsEvent] = relationship(back_populates="velocity_metrics")
