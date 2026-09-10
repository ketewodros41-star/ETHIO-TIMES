"""Data-access layer for news events, memberships, and timelines."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.enums import EventStatus, EventVerificationStatus, EventVerifyStatus, TrendStatus
from app.models.news_event import EventArticle, EventTimeline, NewsEvent
from app.models.verification import EventClaim

_ETHIOPIA_TERMS = [
    "ethiopia", "ethiopian", "abiy", "addis", "amhara", "oromo", "oromia",
    "tigray", "somali region", "afar", "sidama", "fano", "tplf", "birr",
    "gerd", "abbay", "habesha", "diaspora"
]
_NEIGHBORING_TERMS = [
    "eritrea", "somalia", "somaliland", "djibouti", "sudan", "south sudan", "kenya",
    "horn of africa", "red sea", "assab", "mogadishu", "nairobi", "khartoum", "asmara"
]


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, event_id: uuid.UUID) -> NewsEvent | None:
        return self.session.get(NewsEvent, event_id)

    def get_detail(self, event_id: uuid.UUID) -> NewsEvent | None:
        return self.session.scalar(
            select(NewsEvent)
            .options(
                selectinload(NewsEvent.article_links)
                .selectinload(EventArticle.article)
                .selectinload(Article.source),
                selectinload(NewsEvent.timeline),
                selectinload(NewsEvent.claims).selectinload(EventClaim.evidence),
                selectinload(NewsEvent.contradictions),
                selectinload(NewsEvent.velocity_metrics),
            )
            .where(NewsEvent.id == event_id)
        )

    def get_detail_for_compose(self, event_id: uuid.UUID) -> NewsEvent | None:
        return self.get_detail(event_id)

    def get_with_articles(self, event_id: uuid.UUID | str) -> NewsEvent | None:
        """Fetch event with article_links + articles eagerly loaded."""
        from sqlalchemy.orm import joinedload
        from app.models.news_event import EventArticle
        from app.models.article import Article
        if isinstance(event_id, str):
            import uuid as uuid_mod
            event_id = uuid_mod.UUID(event_id)
        return (
            self.session.query(NewsEvent)
            .options(
                joinedload(NewsEvent.article_links).joinedload(EventArticle.article)
            )
            .filter(NewsEvent.id == event_id)
            .first()
        )

    def event_for_article(self, article_id: uuid.UUID) -> NewsEvent | None:
        """Return the event an article belongs to (if any)."""
        return self.session.scalar(
            select(NewsEvent)
            .join(EventArticle, EventArticle.event_id == NewsEvent.id)
            .where(EventArticle.article_id == article_id)
            .limit(1)
        )

    def membership(
        self, event_id: uuid.UUID, article_id: uuid.UUID
    ) -> EventArticle | None:
        return self.session.scalar(
            select(EventArticle).where(
                EventArticle.event_id == event_id,
                EventArticle.article_id == article_id,
            )
        )

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: EventStatus | None = None,
        category: str | None = None,
        search: str | None = None,
        event_verification_status: EventVerificationStatus | None = None,
        review_required: bool | None = None,
        trend_status: TrendStatus | None = None,
        breaking: bool | None = None,
        sort: str = "last_seen",
        scope: str | None = "ethiopia",
    ) -> tuple[list[NewsEvent], int]:
        stmt = select(NewsEvent)
        count_stmt = select(func.count()).select_from(NewsEvent)

        if scope == "ethiopia":
            eth_conds = [
                func.lower(NewsEvent.title).like(f"%{t}%") for t in _ETHIOPIA_TERMS
            ] + [
                func.lower(NewsEvent.summary).like(f"%{t}%") for t in _ETHIOPIA_TERMS
            ] + [
                NewsEvent.primary_region.is_not(None)
            ]
            stmt = stmt.where(or_(*eth_conds))
            count_stmt = count_stmt.where(or_(*eth_conds))
        elif scope == "neighboring":
            all_terms = list(set(_ETHIOPIA_TERMS + _NEIGHBORING_TERMS))
            neigh_conds = [
                func.lower(NewsEvent.title).like(f"%{t}%") for t in all_terms
            ] + [
                func.lower(NewsEvent.summary).like(f"%{t}%") for t in all_terms
            ] + [
                NewsEvent.primary_region.is_not(None)
            ]
            stmt = stmt.where(or_(*neigh_conds))
            count_stmt = count_stmt.where(or_(*neigh_conds))

        if status is not None:
            stmt = stmt.where(NewsEvent.status == status)
            count_stmt = count_stmt.where(NewsEvent.status == status)
        if category:
            stmt = stmt.where(NewsEvent.primary_category == category)
            count_stmt = count_stmt.where(NewsEvent.primary_category == category)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(func.lower(NewsEvent.title).like(pattern))
            count_stmt = count_stmt.where(func.lower(NewsEvent.title).like(pattern))
        if event_verification_status is not None:
            stmt = stmt.where(
                NewsEvent.event_verification_status == event_verification_status
            )
            count_stmt = count_stmt.where(
                NewsEvent.event_verification_status == event_verification_status
            )
        if review_required is not None:
            stmt = stmt.where(NewsEvent.review_required.is_(review_required))
            count_stmt = count_stmt.where(NewsEvent.review_required.is_(review_required))
        if trend_status is not None:
            stmt = stmt.where(NewsEvent.trend_status == trend_status)
            count_stmt = count_stmt.where(NewsEvent.trend_status == trend_status)
        if breaking is True:
            stmt = stmt.where(NewsEvent.breaking_candidate.is_(True))
            count_stmt = count_stmt.where(NewsEvent.breaking_candidate.is_(True))
        elif breaking is False:
            stmt = stmt.where(NewsEvent.breaking_candidate.is_(False))
            count_stmt = count_stmt.where(NewsEvent.breaking_candidate.is_(False))

        total = self.session.scalar(count_stmt) or 0
        if sort == "trend_score":
            order = (
                NewsEvent.trend_score.desc(),
                NewsEvent.last_seen_at.desc().nullslast(),
                NewsEvent.created_at.desc(),
            )
        else:
            order = (
                NewsEvent.last_seen_at.desc().nullslast(),
                NewsEvent.created_at.desc(),
            )
        stmt = stmt.order_by(*order).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all()), total

    def add(self, event: NewsEvent) -> NewsEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def add_membership(self, link: EventArticle) -> EventArticle:
        self.session.add(link)
        self.session.flush()
        return link

    def add_timeline(self, entry: EventTimeline) -> EventTimeline:
        self.session.add(entry)
        self.session.flush()
        return entry

    def member_articles(self, event_id: uuid.UUID) -> list[Article]:
        return list(
            self.session.scalars(
                select(Article)
                .join(EventArticle, EventArticle.article_id == Article.id)
                .where(EventArticle.event_id == event_id)
            ).all()
        )

    def lock_for_verification(self, event_id: uuid.UUID) -> NewsEvent | None:
        """Row-lock an event with SKIP LOCKED so concurrent workers don't collide."""
        return self.session.scalar(
            select(NewsEvent)
            .where(NewsEvent.id == event_id)
            .with_for_update(skip_locked=True)
        )

    def select_pending_verification_ids(self, *, limit: int = 100) -> list[uuid.UUID]:
        """Events whose verification worker still has work to do."""
        stmt = (
            select(NewsEvent.id)
            .where(
                NewsEvent.verification_processing_status.in_(
                    [
                        EventVerifyStatus.pending,
                        EventVerifyStatus.failed,
                    ]
                )
            )
            .order_by(NewsEvent.last_seen_at.desc().nullslast(), NewsEvent.created_at.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def lock_for_trend(self, event_id: uuid.UUID) -> NewsEvent | None:
        """Row-lock an event with SKIP LOCKED for trend recomputation."""
        return self.session.scalar(
            select(NewsEvent)
            .where(NewsEvent.id == event_id)
            .with_for_update(skip_locked=True)
        )

    def select_stale_trend_ids(self, *, limit: int = 100) -> list[uuid.UUID]:
        """Events never scored, with new coverage, or past the freshness window."""
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(minutes=settings.trend_stale_minutes)
        stmt = (
            select(NewsEvent.id)
            .where(
                (NewsEvent.trend_scored_at.is_(None))
                | (NewsEvent.last_seen_at > NewsEvent.trend_scored_at)
                | (NewsEvent.trend_scored_at < cutoff)
            )
            .order_by(
                NewsEvent.last_seen_at.desc().nullslast(),
                NewsEvent.created_at.asc(),
            )
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
