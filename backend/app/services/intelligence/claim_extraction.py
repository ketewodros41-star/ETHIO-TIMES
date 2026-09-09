"""Claim extraction from event articles (Phase 3).

Gemini structured JSON is the primary path. A deterministic fallback mines
``article_analysis`` money/statistics/dates plus regexes for casualties,
percentages, and currency so verification still runs without a live model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderError, TextGenerationRequest
from app.models.article import Article
from app.models.enums import ClaimType
from app.schemas.intelligence import ClaimExtractionResult, ExtractedClaim
from app.services.intelligence import prompts

logger = get_logger(__name__)

_CASUALTY_RE = re.compile(
    r"(\d[\d,]*)\s+(?:people\s+)?(?:killed|dead|died|wounded|injured|casualties)",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(
    r"([\d]+(?:\.\d+)?)\s*(?:percent|%)",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"(?:ETB|USD|US\$|\$|birr)\s*[\d,.]+(?:\s*(?:billion|million|bn|mn|trillion))?"
    r"|[\d,.]+\s*(?:billion|million)?\s*(?:birr|ETB|USD)",
    re.IGNORECASE,
)
_INSTITUTION_RE = re.compile(
    r"\b(national bank of ethiopia|\bNBE\b|ministry of finance|\bMoF\b|"
    r"office of the prime minister|\bPMO\b|ministry of foreign affairs|\bMFA\b|"
    r"ethiopian statistics service|\bESS\b|ethiopian investment commission|\bEIC\b|"
    r"prime minister(?:'s office)?)\b",
    re.IGNORECASE,
)
_GEO_HINTS = (
    "addis ababa",
    "oromia",
    "amhara",
    "tigray",
    "afar",
    "somali",
    "sidama",
    "gambela",
    "benishangul",
    "harari",
    "dire dawa",
    "mekelle",
    "bahir dar",
    "hawassa",
)


def canonical_claim_key(
    claim_type: str, entities: list[str], normalized_value: str | None
) -> str:
    """Stable grouping key so comparable claims can be contradicted."""
    ents = ",".join(sorted({e.strip().lower() for e in entities if e and e.strip()}))
    kind = _value_kind(normalized_value)
    return f"{claim_type}:{ents}:{kind}"


def _value_kind(value: str | None) -> str:
    if not value:
        return "stmt"
    if re.search(r"%|percent", value, re.I):
        return "pct"
    if re.search(r"killed|dead|died|casualt", value, re.I):
        return "casualty"
    if re.search(r"etb|usd|birr|\$|billion|million", value, re.I):
        return "money"
    if re.search(r"\d", value):
        return "num"
    return "stmt"


@dataclass
class ArticleClaimBundle:
    article: Article
    result: ClaimExtractionResult
    used_fallback: bool


class ClaimExtractionService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def extract_for_article(self, article: Article) -> ArticleClaimBundle:
        if self.provider.is_available():
            try:
                data = self.provider.generate_json(
                    TextGenerationRequest(
                        prompt=prompts.claim_extraction_prompt(
                            article.title, article.summary, article.content
                        ),
                        system=prompts.CLAIM_SYSTEM,
                        response_schema=prompts.CLAIM_SCHEMA,
                        max_tokens=2048,
                    )
                )
                result = ClaimExtractionResult.model_validate(data)
                self._ensure_excerpts(article, result)
                return ArticleClaimBundle(article, result, used_fallback=False)
            except (ProviderError, ValidationError) as exc:
                logger.warning(
                    "claim_extraction_gemini_failed_fallback",
                    article_id=str(article.id),
                    error=str(exc),
                )
        return ArticleClaimBundle(
            article, self._fallback(article), used_fallback=True
        )

    def _ensure_excerpts(self, article: Article, result: ClaimExtractionResult) -> None:
        fallback = _excerpt_fallback(article)
        for claim in result.claims:
            if not (claim.excerpt or "").strip():
                claim.excerpt = fallback

    def _fallback(self, article: Article) -> ClaimExtractionResult:
        claims: list[ExtractedClaim] = []
        text = " ".join(
            p for p in (article.title, article.summary, article.content) if p
        )
        analysis = article.analysis
        excerpt = _excerpt_fallback(article)

        if analysis:
            for m in analysis.money or []:
                amount = m.get("amount") if isinstance(m, dict) else None
                currency = m.get("currency") if isinstance(m, dict) else None
                context = m.get("context") if isinstance(m, dict) else None
                if not amount:
                    continue
                value = f"{amount} {currency or ''}".strip()
                claims.append(
                    ExtractedClaim(
                        claim_text=context or f"Reported amount {value}",
                        claim_type=ClaimType.financial.value,
                        normalized_value=value,
                        entities=_gov_entities(analysis),
                        excerpt=_snip(text, amount) or excerpt,
                        is_major=True,
                        confidence=0.45,
                    )
                )
            for s in analysis.statistics or []:
                value = s.get("value") if isinstance(s, dict) else None
                unit = s.get("unit") if isinstance(s, dict) else None
                context = s.get("context") if isinstance(s, dict) else None
                if not value:
                    continue
                nv = f"{value} {unit or ''}".strip()
                claims.append(
                    ExtractedClaim(
                        claim_text=context or f"Reported statistic {nv}",
                        claim_type=ClaimType.statistical.value,
                        normalized_value=nv,
                        entities=_gov_entities(analysis),
                        excerpt=_snip(text, str(value)) or excerpt,
                        is_major=True,
                        confidence=0.45,
                    )
                )
            for d in analysis.dates or []:
                label = d.get("text") if isinstance(d, dict) else None
                if not label:
                    continue
                claims.append(
                    ExtractedClaim(
                        claim_text=d.get("context") or f"Dated {label}",
                        claim_type=ClaimType.timeline.value,
                        normalized_value=d.get("iso") or label,
                        entities=[],
                        excerpt=_snip(text, str(label)) or excerpt,
                        is_major=False,
                        confidence=0.4,
                    )
                )

        for match in _CASUALTY_RE.finditer(text):
            n = match.group(1).replace(",", "")
            claims.append(
                ExtractedClaim(
                    claim_text=match.group(0),
                    claim_type=ClaimType.casualty.value,
                    normalized_value=n,
                    excerpt=_snip(text, match.group(0)) or excerpt,
                    is_major=True,
                    confidence=0.5,
                )
            )
        if not any(c.claim_type == ClaimType.financial.value for c in claims):
            money = _MONEY_RE.search(text)
            if money:
                claims.append(
                    ExtractedClaim(
                        claim_text=money.group(0),
                        claim_type=ClaimType.financial.value,
                        normalized_value=money.group(0).strip(),
                        excerpt=_snip(text, money.group(0)) or excerpt,
                        is_major=True,
                        confidence=0.4,
                    )
                )
        if not any(c.claim_type == ClaimType.statistical.value for c in claims):
            pct = _PERCENT_RE.search(text)
            if pct:
                claims.append(
                    ExtractedClaim(
                        claim_text=pct.group(0),
                        claim_type=ClaimType.statistical.value,
                        normalized_value=f"{pct.group(1)}%",
                        excerpt=_snip(text, pct.group(0)) or excerpt,
                        is_major=True,
                        confidence=0.4,
                    )
                )

        lower = text.lower()
        for hint in _GEO_HINTS:
            if hint in lower:
                claims.append(
                    ExtractedClaim(
                        claim_text=f"Event located in {hint.title()}",
                        claim_type=ClaimType.geographic.value,
                        normalized_value=hint.title(),
                        excerpt=_snip(text, hint) or excerpt,
                        is_major=False,
                        confidence=0.4,
                    )
                )
                break

        if article.title:
            claims.append(
                ExtractedClaim(
                    claim_text=article.title,
                    claim_type=ClaimType.announcement.value,
                    excerpt=excerpt,
                    is_major=True,
                    confidence=0.35,
                )
            )

        institutions = [
            m.group(0).strip() for m in _INSTITUTION_RE.finditer(text)
        ]
        if analysis:
            institutions.extend(_gov_entities(analysis))

        seen_inst: dict[str, str] = {}
        for name in institutions:
            key = name.lower()
            seen_inst.setdefault(key, name)

        return ClaimExtractionResult(
            claims=_dedupe_claims(claims),
            cited_institutions=list(seen_inst.values()),
        )


def _gov_entities(analysis) -> list[str]:  # noqa: ANN001
    ents = analysis.entities or {}
    if isinstance(ents, dict):
        return [str(x) for x in ents.get("government_institutions") or []]
    return []


def _excerpt_fallback(article: Article) -> str:
    for part in (article.summary, article.title, article.content):
        if part and part.strip():
            return part.strip()[:400]
    return "(no excerpt)"


def _snip(text: str, needle: str, window: int = 140) -> str:
    if not text or not needle:
        return ""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window // 4)
    end = min(len(text), idx + len(needle) + window)
    return text[start:end].strip()


def _dedupe_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    seen: set[str] = set()
    out: list[ExtractedClaim] = []
    for c in claims:
        key = f"{c.claim_type}:{c.claim_text.strip().lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
