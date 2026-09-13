"""Context-grounded English-to-Amharic editorial adaptation for Photo Studio."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, TextGenerationRequest
from app.models.news_event import NewsEvent
from app.repositories.event_repository import EventRepository
from app.schemas.social_post import EditorialTranslationRequest, EditorialTranslationResponse
from app.services.social.editorial_layout import (
    EditorialLayoutBudget,
    get_editorial_layout_budget,
    normalise_content_mode,
)

logger = get_logger(__name__)
_ETHIOPIC = re.compile(r"[\u1200-\u137f]")


class TranslationUnavailableError(RuntimeError):
    """The provider did not produce a safe, publishable editorial draft."""


@dataclass(frozen=True)
class _ValidatedDraft:
    headline: str
    dek: str
    category: str
    punchline_words: list[str]
    slide_headers: list[str]
    slide_bodies: list[str]


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _amharic_enough(value: str) -> bool:
    """Allow proper names/numbers but reject an English fallback as translation."""
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return False
    return sum(bool(_ETHIOPIC.match(char)) for char in letters) / len(letters) >= 0.55


def _english_enough(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    return bool(letters) and sum(char.isascii() for char in letters) / len(letters) >= 0.55


class EditorialTranslationService:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.event_repo = EventRepository(session)

    def translate_editorial(self, req: EditorialTranslationRequest) -> EditorialTranslationResponse:
        target_language = req.target_language.lower()
        if target_language not in {"am", "en"}:
            raise TranslationUnavailableError("Only Amharic (am) and English (en) editorial drafts are supported")
        budget = get_editorial_layout_budget(
            theme=req.theme, template=req.template, content_mode=req.content_mode
        )
        mode = normalise_content_mode(req.template, req.content_mode)
        event, facts = self._event_context(req.event_id)
        if not self.provider or not self.provider.is_available():
            raise TranslationUnavailableError("No configured text provider is available for Amharic translation")

        request = TextGenerationRequest(
            system=self._system_prompt(mode, budget, target_language),
            prompt=self._user_prompt(req, event, facts, mode),
            response_schema=self._response_schema(mode),
            temperature=0.1,
            max_tokens=4096,
        )
        providers = (
            getattr(self.provider, "providers", None)
            if hasattr(self.provider, "providers")
            else [self.provider]
        )
        last_exc: Exception | None = None
        for prov in providers:
            try:
                raw = prov.generate_json(request)
                draft = self._validate(raw, budget, mode, target_language)
                active_prov_name = getattr(prov, "name", getattr(self.provider, "name", "ai"))
                return EditorialTranslationResponse(
                    headline=draft.headline,
                    dek=draft.dek,
                    category=draft.category,
                    punchline_words=draft.punchline_words,
                    slide_headers=draft.slide_headers,
                    slide_bodies=draft.slide_bodies,
                    translated_language=target_language,
                    provider=active_prov_name,
                    layout_budget=budget.as_dict(),
                )
            except Exception as exc:
                p_name = getattr(prov, "name", type(prov).__name__)
                logger.warning("editorial_translation_provider_attempt_failed", provider=p_name, error=str(exc))
                last_exc = exc
                continue

        logger.warning("editorial_translation_unavailable", error=str(last_exc), mode=mode)
        raise TranslationUnavailableError(
            "The translation provider did not return a layout-safe Amharic editorial draft"
        ) from last_exc

    def _event_context(self, event_id: Any) -> tuple[NewsEvent | None, list[str]]:
        if not event_id:
            return None, []
        try:
            if isinstance(event_id, str):
                import uuid as _uuid
                event_id = _uuid.UUID(event_id)
            event = self.event_repo.get_detail(event_id)
        except Exception as exc:
            logger.warning("translation_event_context_failed", error=str(exc))
            return None, []
        if not event:
            return None, []
        facts = [
            _clean(claim.claim_text)
            for claim in getattr(event, "claims", [])
            if getattr(claim, "evidence", None) and _clean(getattr(claim, "claim_text", ""))
        ][:5]
        return event, facts

    @staticmethod
    def _system_prompt(mode: str, budget: EditorialLayoutBudget, target_language: str) -> str:
        slide_rule = (
            "Return exactly five slides. Each slide must add a distinct verified fact, context, impact, or source note; never use generic filler."
            if mode == "carousel_5" else "Do not return slide copy for a single-card post."
        )
        return f"""You are ETHIOPIAN TIMES' senior bilingual Amharic broadcast editor.
Adapt news copy into accurate, natural, concise {"Amharic in Ge'ez script" if target_language == "am" else "English"}. This is editorial adaptation, not literal translation.

Non-negotiable rules:
- Preserve people, institutions, locations, dates, numbers, uncertainty, and attribution. Do not invent facts.
- Headline: at most {budget.headline_max_chars} characters and {budget.headline_max_words} words.
- Dek: one concise sentence, at most {budget.dek_max_chars} characters.
- Category: one or two natural Amharic words.
- Choose one to {budget.highlight_max_words} exact words from the headline as `punchline_words`.
- {"Use Ethiopic script except unavoidable proper names, acronyms, or numerals." if target_language == "am" else "Use clear international-news English; retain proper names and figures exactly."}
- {slide_rule}
Return only a JSON object matching the supplied schema."""

    @staticmethod
    def _user_prompt(
        req: EditorialTranslationRequest,
        event: NewsEvent | None,
        facts: list[str],
        mode: str,
    ) -> str:
        event_lines: list[str] = []
        if event:
            event_lines.extend([
                f"EVENT TITLE: {event.title}",
                f"EVENT SUMMARY: {event.summary or ''}",
                f"EVENT CATEGORY: {event.primary_category or 'news'}",
                f"EVENT REGION: {event.primary_region or 'Ethiopia'}",
            ])
        if facts:
            event_lines.append("VERIFIED FACTS:\n" + "\n".join(f"- {fact}" for fact in facts))
        source_slides = "\n".join(
            f"Slide {index + 1}: header={header!r}; body={body!r}"
            for index, (header, body) in enumerate(zip(req.slide_headers, req.slide_bodies))
            if header or body
        )
        return f"""REQUESTED LAYOUT: theme={req.theme}; mode={mode}; format={req.format}
{chr(10).join(event_lines)}

SOURCE COPY TO ADAPT:
Headline: {req.headline}
Dek: {req.dek or ''}
Category: {req.category or 'news'}

EXISTING CAROUSEL COPY (translate/adapt each when supplied):
{source_slides or 'No existing slide copy; derive only from verified facts and supplied source copy.'}

Do not claim that information is verified unless it is in the event context. Fit every field to the requested layout budget."""

    @staticmethod
    def _response_schema(mode: str) -> dict[str, object]:
        properties = {
            "headline": {"type": "string"}, "dek": {"type": "string"},
            "category": {"type": "string"},
            "punchline_words": {"type": "array", "items": {"type": "string"}},
            "slide_headers": {"type": "array", "items": {"type": "string"}},
            "slide_bodies": {"type": "array", "items": {"type": "string"}},
        }
        required = ["headline", "dek", "category", "punchline_words"]
        if mode == "carousel_5":
            required.extend(["slide_headers", "slide_bodies"])
        return {"type": "object", "properties": properties, "required": required}

    @staticmethod
    def _validate(raw: object, budget: EditorialLayoutBudget, mode: str, target_language: str) -> _ValidatedDraft:
        if not isinstance(raw, dict):
            raise ValueError("provider response is not an object")
        headline, dek, category = (_clean(raw.get(key)) for key in ("headline", "dek", "category"))
        if not headline or not dek or not category:
            raise ValueError("translation is missing a required editorial field")

        # Gracefully handle headline word/char budget
        hl_words = headline.split()
        max_hl_words = max(budget.headline_max_words, 12)
        if len(hl_words) > max_hl_words:
            headline = " ".join(hl_words[:max_hl_words])

        max_hl_chars = budget.headline_max_chars + 15
        if len(headline) > max_hl_chars:
            cut = headline[:budget.headline_max_chars]
            headline = cut.rsplit(" ", 1)[0] if " " in cut else cut

        # Gracefully handle dek length
        max_dek_chars = budget.dek_max_chars + 30
        if len(dek) > max_dek_chars:
            cut = dek[:budget.dek_max_chars]
            dek = cut.rsplit("።", 1)[0] + "።" if "።" in cut else (cut.rsplit(" ", 1)[0] + "...")

        cat_words = category.split()
        if len(cat_words) > 2:
            category = " ".join(cat_words[:2])

        language_check = _amharic_enough if target_language == "am" else _english_enough
        if not all(language_check(value) for value in (headline, dek, category)):
            raise ValueError(f"translation is not sufficiently {target_language}")

        # Highlights / punchline words: extract valid matching words or select directly from headline
        normalized_headline = headline.casefold()
        raw_highlights = [_clean(value) for value in raw.get("punchline_words", []) if _clean(value)]
        valid_highlights = [h for h in raw_highlights if h.casefold() in normalized_headline]
        if not valid_highlights:
            # Pick up to 2 salient tokens directly from headline
            tokens = [w for w in headline.split() if len(w) > 2]
            valid_highlights = tokens[:min(2, budget.highlight_max_words)] if tokens else headline.split()[:1]

        highlights = valid_highlights[:budget.highlight_max_words]

        headers = [_clean(value) for value in raw.get("slide_headers", [])]
        bodies = [_clean(value) for value in raw.get("slide_bodies", [])]
        if mode == "carousel_5":
            if len(headers) != budget.slide_count or len(bodies) != budget.slide_count:
                raise ValueError("carousel requires exactly five translated slides")
            if any(not header or not body for header, body in zip(headers, bodies)):
                raise ValueError("carousel contains an empty slide")
            if budget.slide_header_max_chars:
                headers = [h[:budget.slide_header_max_chars] if len(h) > budget.slide_header_max_chars else h for h in headers]
            if budget.slide_body_max_chars:
                bodies = [b[:budget.slide_body_max_chars] if len(b) > budget.slide_body_max_chars else b for b in bodies]
            if not all(language_check(value) for value in headers + bodies):
                raise ValueError(f"carousel is not sufficiently {target_language}")
            if len({header.casefold() for header in headers}) != budget.slide_count:
                raise ValueError("carousel slide headers must be distinct")
        else:
            headers, bodies = [], []
        return _ValidatedDraft(headline, dek, category, highlights, headers, bodies)
