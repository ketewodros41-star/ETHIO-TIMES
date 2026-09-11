"""Event verification orchestrator (Phase 3).

Runs after clustering:

    claims → evidence mapping → contradictions → primary-source discovery
    → sensitive-news rules → score/status persist

Idempotent: a completed run is skipped unless new coverage arrived
(``last_seen_at`` after ``verified_at``) or the caller passes ``force``.
Re-runs replace prior claims/contradictions for the event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider
from app.models.article import Article
from app.models.enums import (
    ContradictionSeverity,
    EventVerificationStatus,
    EventVerifyStatus,
)
from app.models.news_event import EventArticle, NewsEvent
from app.models.verification import Contradiction, EventClaim
from app.services.intelligence.claim_extraction import ClaimExtractionService
from app.services.intelligence.contradiction_service import (
    ContradictionService,
    DetectedContradiction,
)
from app.services.intelligence.evidence_mapping import EvidenceMappingService
from app.services.intelligence.primary_source import PrimarySourceService
from app.services.intelligence.scoring import score_event
from app.services.intelligence.sensitive_rules import evaluate_sensitive

logger = get_logger(__name__)

_MAJOR_CONFLICT = {ContradictionSeverity.high, ContradictionSeverity.critical}


@dataclass
class VerificationResult:
    event_id: str
    skipped: bool = False
    final_status: EventVerifyStatus = EventVerifyStatus.pending
    verification_status: EventVerificationStatus | None = None
    score: int | None = None
    claim_count: int = 0
    contradiction_count: int = 0
    error: str | None = None
    steps_run: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "skipped": self.skipped,
            "final_status": self.final_status.value,
            "verification_status": (
                self.verification_status.value if self.verification_status else None
            ),
            "score": self.score,
            "claim_count": self.claim_count,
            "contradiction_count": self.contradiction_count,
            "error": self.error,
            "steps_run": self.steps_run,
        }


class VerificationPipeline:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.claims = ClaimExtractionService(provider)
        self.evidence = EvidenceMappingService(session)
        self.contradictions = ContradictionService(session, provider)
        self.primary = PrimarySourceService(session)

    def process(self, event: NewsEvent, *, force: bool = False) -> VerificationResult:
        result = VerificationResult(
            event_id=str(event.id),
            final_status=event.verification_processing_status,
        )
        if self._should_skip(event, force=force):
            result.skipped = True
            result.verification_status = event.event_verification_status
            result.score = event.verification_score
            return result

        event.verification_processing_status = EventVerifyStatus.verifying
        self.session.flush()

        try:
            articles = self._load_articles(event.id)
            self._clear_previous(event.id)
            result.steps_run.append("reset")

            cited: list[str] = []
            persisted_claims: list[EventClaim] = []
            cap = settings.verification_max_articles_for_llm
            for article in articles[:cap]:
                bundle = self.claims.extract_for_article(article)
                cited.extend(bundle.result.cited_institutions)
                rows = self.evidence.persist_bundle(event.id, bundle)
                persisted_claims.extend(r.claim for r in rows)
            # Remaining articles still contribute fallback extraction without
            # extra Gemini calls when we already hit the cap.
            if len(articles) > cap:
                fallback_only = ClaimExtractionService(
                    _UnavailableProvider(self.provider)
                )
                for article in articles[cap:]:
                    bundle = fallback_only.extract_for_article(article)
                    cited.extend(bundle.result.cited_institutions)
                    rows = self.evidence.persist_bundle(event.id, bundle)
                    persisted_claims.extend(r.claim for r in rows)
            result.steps_run.append("claims")
            result.claim_count = len(persisted_claims)

            detected = self.contradictions.detect(event.id, persisted_claims)
            result.steps_run.append("contradictions")
            result.contradiction_count = len(detected)

            discovery = self.primary.discover(
                event_id=event.id,
                articles=articles,
                cited_institutions=cited,
            )
            result.steps_run.append("primary_source")

            sensitive = evaluate_sensitive(event, articles)
            result.steps_run.append("sensitive")

            scoring = score_event(
                articles=articles,
                claims=persisted_claims,
                contradictions=detected,
                primary_source_available=discovery.available,
            )
            result.steps_run.append("score")

            review_reasons = list(sensitive.reasons)
            review_required = sensitive.sensitive
            if any(d.severity in _MAJOR_CONFLICT for d in detected):
                review_required = True
                review_reasons.append("major_contradiction")
            elif detected:
                review_reasons.append("contradictions_present")

            auto_publish = _auto_publish_eligible(
                sensitive=sensitive.sensitive,
                contradictions=detected,
                review_required=review_required,
                status=scoring.status,
                score=scoring.score,
            )

            event.verification_score = scoring.score
            event.event_verification_status = scoring.status
            event.verification_explanation = {
                **scoring.explanation,
                "sensitive_categories": sensitive.categories,
                "cited_institutions": discovery.cited_institutions,
                "discovered_primary_sources": discovery.matched_names,
                "review_reasons": review_reasons,
                "auto_publish_eligible": auto_publish,
            }
            event.primary_source_available = discovery.available
            event.cited_institutions = discovery.cited_institutions
            event.discovered_primary_source_ids = discovery.matched_source_ids
            event.review_required = review_required
            event.review_reasons = review_reasons
            event.auto_publish_eligible = auto_publish
            event.verification_processing_status = EventVerifyStatus.verified
            event.last_verification_error = None
            event.verified_at = datetime.now(UTC)
            self.session.flush()

            result.final_status = EventVerifyStatus.verified
            result.verification_status = scoring.status
            result.score = scoring.score
            logger.info(
                "event_verified",
                event_id=result.event_id,
                score=scoring.score,
                status=scoring.status.value,
                claims=result.claim_count,
                contradictions=result.contradiction_count,
                review_required=review_required,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            self.session.rollback()
            fresh = self.session.get(NewsEvent, event.id)
            if fresh is not None:
                fresh.verification_attempts += 1
                fresh.last_verification_error = f"{type(exc).__name__}: {exc}"[:2000]
                if fresh.verification_attempts >= settings.verification_max_attempts:
                    fresh.verification_processing_status = EventVerifyStatus.dead_letter
                else:
                    fresh.verification_processing_status = EventVerifyStatus.failed
                result.final_status = fresh.verification_processing_status
            result.error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "verification_failed", event_id=result.event_id, error=result.error
            )
            return result

    def _should_skip(self, event: NewsEvent, *, force: bool) -> bool:
        if force:
            return False
        if event.verification_processing_status != EventVerifyStatus.verified:
            return False
        if event.verified_at is None:
            return False
        if event.last_seen_at and event.last_seen_at > event.verified_at:
            return False
        return True

    def _load_articles(self, event_id) -> list[Article]:  # noqa: ANN001
        stmt = (
            select(Article)
            .join(EventArticle, EventArticle.article_id == Article.id)
            .where(EventArticle.event_id == event_id)
            .options(selectinload(Article.source), selectinload(Article.analysis))
        )
        return list(self.session.scalars(stmt).all())

    def _clear_previous(self, event_id) -> None:  # noqa: ANN001
        self.session.execute(
            delete(Contradiction).where(Contradiction.event_id == event_id)
        )
        self.session.execute(delete(EventClaim).where(EventClaim.event_id == event_id))
        self.session.flush()


def _auto_publish_eligible(
    *,
    sensitive: bool,
    contradictions: list[DetectedContradiction],
    review_required: bool,
    status: EventVerificationStatus,
    score: int,
) -> bool:
    """Auto-publish is opt-in and conservative.

    Sensitive categories never auto-publish. Any contradiction disables the
    flag. Remaining bar: confirmed status, human review not required, and
    score at/above ``verification_auto_publish_min_score``.
    """
    if sensitive or contradictions or review_required:
        return False
    if status != EventVerificationStatus.confirmed:
        return False
    return score >= settings.verification_auto_publish_min_score


class _UnavailableProvider:
    """Wraps a provider but reports unavailable so leftover articles use fallback."""

    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner
        self.name = getattr(inner, "name", "fallback")

    def is_available(self) -> bool:
        return False

    def generate_json(self, request):  # noqa: ANN001
        return self._inner.generate_json(request)

    def embed(self, texts, task_type="RETRIEVAL_DOCUMENT"):  # noqa: ANN001
        return self._inner.embed(texts, task_type=task_type)
