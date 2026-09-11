"""Persist claim–evidence links (Phase 3).

Editorial later may only use claims that have at least one evidence row
(excerpt + source article URL). Claims that cannot be evidenced are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.article import Article
from app.models.enums import ClaimType
from app.models.verification import ClaimEvidence, EventClaim
from app.schemas.intelligence import ExtractedClaim
from app.services.intelligence.claim_extraction import (
    ArticleClaimBundle,
    canonical_claim_key,
)

logger = get_logger(__name__)


@dataclass
class PersistedClaim:
    claim: EventClaim
    evidence: ClaimEvidence


class EvidenceMappingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def persist_bundle(
        self, event_id, bundle: ArticleClaimBundle  # noqa: ANN001
    ) -> list[PersistedClaim]:
        persisted: list[PersistedClaim] = []
        article = bundle.article
        model_name = "fallback" if bundle.used_fallback else "gemini"
        for extracted in bundle.result.claims:
            row = self._persist_one(event_id, article, extracted, model_name)
            if row is not None:
                persisted.append(row)
        return persisted

    def _persist_one(
        self,
        event_id,  # noqa: ANN001
        article: Article,
        extracted: ExtractedClaim,
        model_name: str,
    ) -> PersistedClaim | None:
        excerpt = (extracted.excerpt or "").strip()
        if not excerpt:
            excerpt = (article.summary or article.title or "").strip()[:400]
        if not excerpt:
            logger.info(
                "claim_dropped_no_evidence",
                article_id=str(article.id),
                claim=extracted.claim_text[:80],
            )
            return None

        claim = EventClaim(
            event_id=event_id,
            article_id=article.id,
            claim_text=extracted.claim_text.strip(),
            claim_type=ClaimType(extracted.claim_type),
            normalized_value=extracted.normalized_value,
            entities=extracted.entities,
            canonical_key=canonical_claim_key(
                extracted.claim_type, extracted.entities, extracted.normalized_value
            ),
            confidence=extracted.confidence,
            is_major=extracted.is_major,
            model=model_name,
            raw=extracted.model_dump(),
        )
        self.session.add(claim)
        self.session.flush()

        evidence = ClaimEvidence(
            claim_id=claim.id,
            article_id=article.id,
            source_id=article.source_id,
            excerpt=excerpt[:1000],
            url=article.url or article.canonical_url,
        )
        self.session.add(evidence)
        self.session.flush()
        claim.evidence.append(evidence)
        return PersistedClaim(claim=claim, evidence=evidence)
