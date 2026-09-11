"""Event lifecycle management (Phase 2).

Assigns a clustered article to an existing event or creates a new one, maintains
membership relation types, counts, centroid, key entities, status, and appends
timeline entries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.models.article import Article
from app.models.enums import (
    ArticleRelationType,
    EventStatus,
    EventTimelineType,
    EventVerifyStatus,
)
from app.models.news_event import EventArticle, EventTimeline, NewsEvent
from app.repositories.event_repository import EventRepository
from app.services.intelligence.clustering_service import ClusterMatch

logger = get_logger(__name__)

# How long after an event's first report a same-event article is a "follow up".
_FOLLOW_UP_AFTER = timedelta(hours=24)

_RELATION_MAP = {
    "duplicate": ArticleRelationType.duplicate,
    "same_event": ArticleRelationType.related,
    "related": ArticleRelationType.context,
}


def _event_time(article: Article) -> datetime:
    return article.published_at or article.fetched_at or datetime.now(UTC)


def _slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in (text or "")[:80]]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "event"


class EventService:
    def __init__(self, session) -> None:  # noqa: ANN001
        self.session = session
        self.repo = EventRepository(session)

    def assign(self, article: Article, match: ClusterMatch | None) -> NewsEvent:
        """Attach `article` to an event (existing or new). Returns the event."""
        if match is None:
            return self._create_event(article)

        event = self.repo.event_for_article(match.article.id)
        if event is None:
            # The matched article has no event yet: create one anchored on it,
            # then attach the new article to it.
            event = self._create_event(match.article)

        relation = self._resolve_relation(article, event, match.relation)
        self._attach(article, event, match, relation)
        self._recompute(event)
        return event

    def ensure_event_for_article(self, article: Article) -> NewsEvent:
        """Return the event the article belongs to, or create a new event anchored on it."""
        existing = self.repo.event_for_article(article.id)
        if existing is not None:
            return existing
        event = self._create_event(article)
        self.session.commit()
        return event

    # -- creation & attachment --------------------------------------------- #
    def _create_event(self, primary: Article) -> NewsEvent:
        existing = self.repo.event_for_article(primary.id)
        if existing is not None:
            return existing

        category = (
            primary.analysis.category
            if primary.analysis and primary.analysis.category
            else (primary.categories[0] if primary.categories else None)
        )
        entities = list(primary.analysis.entity_names) if primary.analysis and primary.analysis.entity_names else []
        occurred = _event_time(primary)
        event = NewsEvent(
            title=primary.title or "(untitled event)",
            summary=(
                primary.analysis.summary
                if primary.analysis and primary.analysis.summary
                else primary.summary
            ),
            slug=_slugify(primary.title or ""),
            status=EventStatus.developing,
            primary_category=category,
            primary_region=primary.primary_region,
            categories=primary.categories if primary.categories else ([category] if category else []),
            key_entities=entities[:25],
            significance_score=float(primary.importance_score or primary.relevance_score or 0.0),
            cluster_confidence=1.0,
            first_seen_at=occurred,
            last_seen_at=occurred,
        )
        self.repo.add(event)
        self.repo.add_membership(
            EventArticle(
                event_id=event.id,
                article_id=primary.id,
                relation_type=ArticleRelationType.primary,
                similarity_score=1.0,
                confidence=1.0,
                is_primary=True,
            )
        )
        self.repo.add_timeline(
            EventTimeline(
                event_id=event.id,
                article_id=primary.id,
                entry_type=EventTimelineType.first_report,
                occurred_at=occurred,
                title=primary.title,
                detail={"source_id": str(primary.source_id)},
            )
        )
        self._recompute(event)
        logger.info("event_created", event_id=str(event.id), primary=str(primary.id))
        return event

    def _resolve_relation(
        self, article: Article, event: NewsEvent, relation: str
    ) -> ArticleRelationType:
        if relation == "same_event" and event.first_seen_at is not None:
            if _event_time(article) - event.first_seen_at >= _FOLLOW_UP_AFTER:
                return ArticleRelationType.follow_up
        return _RELATION_MAP.get(relation, ArticleRelationType.related)

    def _attach(
        self,
        article: Article,
        event: NewsEvent,
        match: ClusterMatch,
        relation: ArticleRelationType,
    ) -> None:
        if self.repo.membership(event.id, article.id) is not None:
            return  # idempotent
        self.repo.add_membership(
            EventArticle(
                event_id=event.id,
                article_id=article.id,
                relation_type=relation,
                similarity_score=match.composite,
                confidence=match.confidence,
                is_primary=False,
            )
        )
        occurred = _event_time(article)
        if relation == ArticleRelationType.duplicate:
            entry_type = EventTimelineType.source_confirmation
        elif relation == ArticleRelationType.follow_up:
            entry_type = EventTimelineType.new_development
        else:
            entry_type = EventTimelineType.source_confirmation
        self.repo.add_timeline(
            EventTimeline(
                event_id=event.id,
                article_id=article.id,
                entry_type=entry_type,
                occurred_at=occurred,
                title=article.title,
                detail={"relation": relation.value, "source_id": str(article.source_id)},
            )
        )
        # New coverage invalidates the previous verification run.
        event.verification_processing_status = EventVerifyStatus.pending
        event.verification_attempts = 0
        event.last_verification_error = None

    # -- aggregate recomputation ------------------------------------------- #
    def _recompute(self, event: NewsEvent) -> None:
        members = self.repo.member_articles(event.id)
        event.article_count = len(members)
        event.source_count = len({m.source_id for m in members})

        times = [_event_time(m) for m in members]
        if times:
            event.first_seen_at = min(times)
            event.last_seen_at = max(times)
        event.significance_score = max(
            (float(m.importance_score or 0.0) for m in members), default=0.0
        )

        # Aggregate key entities across members.
        entity_names: dict[str, None] = {}
        for m in members:
            if m.analysis and m.analysis.entity_names:
                for name in m.analysis.entity_names:
                    entity_names.setdefault(str(name), None)
        event.key_entities = list(entity_names)[:40]

        # Recompute centroid from member embeddings (mean, L2-normalized).
        vectors = [m.embedding for m in members if m.embedding is not None]
        if vectors:
            event.centroid_embedding = _mean_normalized(vectors)

        # Status transitions.
        if event.article_count >= 2 and event.status == EventStatus.developing:
            event.status = EventStatus.updated
        if event.source_count >= 3:
            event.status = EventStatus.confirmed


def _mean_normalized(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            acc[i] += v[i]
    n = len(vectors)
    mean = [x / n for x in acc]
    norm = sum(x * x for x in mean) ** 0.5
    if norm <= 0:
        return mean
    return [x / norm for x in mean]
