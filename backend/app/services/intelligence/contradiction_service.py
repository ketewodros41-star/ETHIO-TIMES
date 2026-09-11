"""Cross-source contradiction detection (Phase 3).

Compares claims across sources. Gemini is used when available; a numeric /
canonical-key heuristic always runs so CI and keyless local runs still flag
conflicting casualty counts and financial figures.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderError, TextGenerationRequest
from app.models.enums import ContradictionSeverity
from app.models.verification import Contradiction, EventClaim
from app.schemas.intelligence import ContradictionDetectionResult
from app.services.intelligence import prompts

logger = get_logger(__name__)

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

_SEVERITY_RANK = {
    ContradictionSeverity.low: 1,
    ContradictionSeverity.medium: 2,
    ContradictionSeverity.high: 3,
    ContradictionSeverity.critical: 4,
}


@dataclass
class DetectedContradiction:
    claim_a: EventClaim
    claim_b: EventClaim
    description: str
    severity: ContradictionSeverity
    source: str  # "gemini" | "heuristic"


class ContradictionService:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider

    def detect(self, event_id, claims: list[EventClaim]) -> list[DetectedContradiction]:
        if len(claims) < 2:
            return []

        heuristic = self._heuristic(claims)
        gemini_pairs: list[DetectedContradiction] = []
        if self.provider.is_available():
            try:
                gemini_pairs = self._via_gemini(claims)
            except (ProviderError, ValidationError, IndexError, KeyError) as exc:
                logger.warning(
                    "contradiction_gemini_failed_heuristic",
                    event_id=str(event_id),
                    error=str(exc),
                )

        merged = _merge(heuristic + gemini_pairs)
        persisted: list[DetectedContradiction] = []
        for item in merged:
            row = Contradiction(
                event_id=event_id,
                claim_a_id=item.claim_a.id,
                claim_b_id=item.claim_b.id,
                description=item.description,
                severity=item.severity,
                details={
                    "source": item.source,
                    "claim_a_text": item.claim_a.claim_text,
                    "claim_b_text": item.claim_b.claim_text,
                    "claim_a_value": item.claim_a.normalized_value,
                    "claim_b_value": item.claim_b.normalized_value,
                },
            )
            self.session.add(row)
            persisted.append(item)
        self.session.flush()
        return persisted

    def _via_gemini(self, claims: list[EventClaim]) -> list[DetectedContradiction]:
        payload = [
            {
                "claim_type": c.claim_type.value,
                "normalized_value": c.normalized_value,
                "entities": c.entities,
                "claim_text": c.claim_text,
            }
            for c in claims
        ]
        data = self.provider.generate_json(
            TextGenerationRequest(
                prompt=prompts.contradiction_prompt(payload),
                system=prompts.CONTRADICTION_SYSTEM,
                response_schema=prompts.CONTRADICTION_SCHEMA,
                max_tokens=2048,
            )
        )
        result = ContradictionDetectionResult.model_validate(data)
        out: list[DetectedContradiction] = []
        n = len(claims)
        for pair in result.contradictions:
            if pair.claim_a_index == pair.claim_b_index:
                continue
            if not (0 <= pair.claim_a_index < n and 0 <= pair.claim_b_index < n):
                continue
            a, b = claims[pair.claim_a_index], claims[pair.claim_b_index]
            if a.article_id and b.article_id and a.article_id == b.article_id:
                # Same article restating itself is not a cross-source conflict.
                continue
            out.append(
                DetectedContradiction(
                    claim_a=a,
                    claim_b=b,
                    description=pair.description or "Conflicting claims",
                    severity=ContradictionSeverity(pair.severity),
                    source="gemini",
                )
            )
        return out

    def _heuristic(self, claims: list[EventClaim]) -> list[DetectedContradiction]:
        out: list[DetectedContradiction] = []
        by_key: dict[str, list[EventClaim]] = {}
        for c in claims:
            key = c.canonical_key or f"{c.claim_type.value}:unknown"
            by_key.setdefault(key, []).append(c)

        for group in by_key.values():
            if len(group) < 2:
                continue
            for a, b in itertools.combinations(group, 2):
                if a.article_id and b.article_id and a.article_id == b.article_id:
                    continue
                conflict = _numeric_conflict(a, b)
                if conflict is None:
                    continue
                out.append(conflict)

        # Geographic: same type, different normalized places.
        geos = [c for c in claims if c.claim_type.value == "geographic"]
        for a, b in itertools.combinations(geos, 2):
            va = (a.normalized_value or "").strip().lower()
            vb = (b.normalized_value or "").strip().lower()
            if va and vb and va != vb and not (va in vb or vb in va):
                out.append(
                    DetectedContradiction(
                        claim_a=a,
                        claim_b=b,
                        description=(
                            f"Locations differ: {a.normalized_value} vs "
                            f"{b.normalized_value}"
                        ),
                        severity=ContradictionSeverity.medium,
                        source="heuristic",
                    )
                )
        return out


def _numeric_conflict(
    a: EventClaim, b: EventClaim
) -> DetectedContradiction | None:
    na, nb = _first_number(a.normalized_value), _first_number(b.normalized_value)
    if na is None or nb is None:
        return None
    if na == nb:
        return None
    # Relative difference; treat small rounding as agreement.
    denom = max(abs(na), abs(nb), 1.0)
    rel = abs(na - nb) / denom
    if rel < 0.05 and a.claim_type.value != "casualty":
        return None

    ctype = a.claim_type.value
    if ctype == "casualty":
        severity = ContradictionSeverity.critical
    elif ctype in {"financial", "statistical"}:
        severity = (
            ContradictionSeverity.high if rel >= 0.2 else ContradictionSeverity.medium
        )
    elif ctype == "timeline":
        severity = ContradictionSeverity.medium
    else:
        severity = ContradictionSeverity.low

    return DetectedContradiction(
        claim_a=a,
        claim_b=b,
        description=(
            f"{ctype} values conflict: {a.normalized_value} vs {b.normalized_value}"
        ),
        severity=severity,
        source="heuristic",
    )


def _first_number(value: str | None) -> float | None:
    if not value:
        return None
    m = _NUM_RE.search(value.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _merge(items: list[DetectedContradiction]) -> list[DetectedContradiction]:
    best: dict[tuple, DetectedContradiction] = {}
    for item in items:
        key = tuple(sorted((str(item.claim_a.id), str(item.claim_b.id))))
        existing = best.get(key)
        if existing is None or _SEVERITY_RANK[item.severity] > _SEVERITY_RANK[
            existing.severity
        ]:
            best[key] = item
    return list(best.values())


def max_severity(
    items: list[DetectedContradiction],
) -> ContradictionSeverity | None:
    if not items:
        return None
    return max(items, key=lambda x: _SEVERITY_RANK[x.severity]).severity
