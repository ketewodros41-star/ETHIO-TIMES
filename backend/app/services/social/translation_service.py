"""Editorial Translation Service (Photo Studio & Social Broadcast).

Translates and adapts English news copy into punchy, authentic, concise Amharic
specifically tailored for Instagram broadcast graphics (Portrait, Square, Story,
Breaking News cards, and Carousel slides).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, TextGenerationRequest
from app.models.news_event import NewsEvent
from app.repositories.event_repository import EventRepository
from app.schemas.social_post import (
    EditorialTranslationRequest,
    EditorialTranslationResponse,
)

logger = get_logger(__name__)

# Standard Ethiopian Category Translations
CATEGORY_TRANSLATIONS: dict[str, str] = {
    "politics": "ፖለቲካ",
    "economy": "ኢኮኖሚ",
    "business": "ቢዝነስና ንግድ",
    "finance": "ፋይናንስ",
    "sports": "ስፖርት",
    "athletics": "አትሌቲክስ",
    "football": "እግር ኳስ",
    "tech": "ቴክኖሎጂ",
    "technology": "ቴክኖሎጂ",
    "culture": "ባህልና ማኅበረሰብ",
    "society": "ማኅበራዊ",
    "breaking": "ሰበር ዜና",
    "security": "ጸጥታና ደህንነት",
    "conflict": "ግጭትና ጸጥታ",
    "diplomacy": "ዲፕሎማሲ",
    "regional": "ቀጣናዊ ጉዳዮች",
    "humanitarian": "ሰብዓዊ ድጋፍ",
    "general": "ዜና",
    "news": "ዜና",
}


class EditorialTranslationService:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.event_repo = EventRepository(session)

    def translate_editorial(
        self, req: EditorialTranslationRequest
    ) -> EditorialTranslationResponse:
        """Translate headline, dek, category and carousel slides into punchy Amharic."""
        event: NewsEvent | None = None
        event_context = ""

        if req.event_id:
            try:
                event = self.event_repo.get_with_articles(req.event_id)
                if event:
                    event_context = (
                        f"STORY CONTEXT:\n"
                        f"- Event Title: {event.title}\n"
                        f"- Event Summary: {event.summary or 'N/A'}\n"
                        f"- Primary Category: {event.primary_category or 'General'}\n"
                        f"- Primary Region: {event.primary_region or 'Ethiopia'}\n"
                    )
                    if getattr(event, "claims", None):
                        evidenced = [
                            c.claim_text for c in event.claims if getattr(c, "evidence", None)
                        ][:4]
                        if evidenced:
                            event_context += "- Verified Facts:\n  * " + "\n  * ".join(evidenced) + "\n"
            except Exception as e:
                logger.warning("failed_to_fetch_event_context", error=str(e))

        target_lang = "Amharic (አማርኛ)" if req.target_language == "am" else req.target_language
        layout_note = f"Format: {req.format} ({req.template} template layout)"

        system_prompt = (
            "You are the Chief Amharic Bilingual Editor and Visual Copy Director at ETHIOPIAN TIMES.\n"
            "Your mission is to craft authentic, punchy, concise broadcast Amharic text for high-impact social news cards.\n\n"
            "STRICT EDITORIAL RULES:\n"
            "1. HEADLINE: Must be exactly 4 to 7 words in Amharic. Action-packed, clear, immediate. Never use wordy or robotic literal translations. Write like top Ethiopian newsrooms (EBC, FBC, Tikvah, Addis Standard).\n"
            "2. DEK / SUBHEADING: Exactly 1 concise Amharic sentence (max 15-20 words) giving essential context or consequence.\n"
            "3. CATEGORY: Exactly 1 or 2 words in Amharic (e.g. ፖለቲካ, ኢኮኖሚ, ስፖርት, ቴክኖሎጂ, ሰበር ዜና, ዲፕሎማሲ).\n"
            "4. PUNCHLINE_WORDS: Select 1 to 3 most impactful words directly from the generated Amharic headline to highlight visually.\n"
            "5. CAROUSEL SLIDES (if applicable): Provide concise Amharic headers and bodies for the 5-slide breakdown.\n"
            "Output ONLY a valid JSON object."
        )

        user_prompt = (
            f"{event_context}\n"
            f"INPUT ENGLISH TEXT:\n"
            f"- Headline: {req.headline}\n"
            f"- Dek/Subheading: {req.dek or 'N/A'}\n"
            f"- Category: {req.category or 'General'}\n"
            f"- Layout: {layout_note}\n\n"
            f"Translate and adapt this content into {target_lang}. "
            f"Ensure the headline is punchy (4-7 words), the dek is 1 crisp sentence, "
            f"and pick 1-3 punchline words from the headline for color highlighting."
        )

        response_schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "Punchy 4-7 word Amharic headline"},
                "dek": {"type": "string", "description": "1 concise Amharic sentence"},
                "category": {"type": "string", "description": "1-2 word Amharic category"},
                "punchline_words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "1 to 3 words from the headline to highlight",
                },
                "slide_headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Amharic headers for carousel slides 1 to 5",
                },
                "slide_bodies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Amharic body texts for carousel slides 1 to 5",
                },
            },
            "required": ["headline", "dek", "category", "punchline_words"],
        }

        # Attempt AI translation
        if self.provider and self.provider.is_available():
            try:
                gen_req = TextGenerationRequest(
                    prompt=user_prompt,
                    system=system_prompt,
                    response_schema=response_schema,
                    temperature=0.2,
                    max_tokens=4096,
                )
                res = self.provider.generate_json(gen_req)
                if isinstance(res, dict) and res.get("headline"):
                    translated_headline = str(res.get("headline", "")).strip()
                    translated_dek = str(res.get("dek", "")).strip()
                    cat_val = str(res.get("category", "")).strip()
                    punchlines = res.get("punchline_words", [])
                    if isinstance(punchlines, str):
                        punchlines = [punchlines]

                    headers = res.get("slide_headers") or [
                        translated_headline,
                        "ዋና ዋና ነጥቦች",
                        "የተረጋገጡ ዝርዝሮች",
                        "ለምን አሳሳቢ ሆነ?",
                        "የተረጋገጠ መረጃ",
                    ]
                    bodies = res.get("slide_bodies") or [
                        translated_dek,
                        "• ቁልፍ የውሳኔ ነጥቦች\n• የተረጋገጠ መረጃ ዝርዝር",
                        "በተለያዩ የመረጃ ምንጮች የተረጋገጠ ተጨማሪ መረጃ።",
                        "ይህ ክስተት በኢትዮጵያና በቀጠናው ላይ ከፍተኛ ተጽዕኖ ይኖረዋል።",
                        "መረጃው በETHIOPIAN TIMES የዜና ማረጋገጫ ክፍል ተረጋግጧል።",
                    ]

                    return EditorialTranslationResponse(
                        headline=translated_headline,
                        dek=translated_dek,
                        category=cat_val,
                        punchline_words=[str(w).strip() for w in punchlines if w],
                        slide_headers=headers,
                        slide_bodies=bodies,
                        translated_language="am",
                    )
            except Exception as exc:
                logger.warning("ai_translation_call_failed", error=str(exc))

        # Deterministic Fallback if AI unavailable or offline
        cat_key = (req.category or (event.primary_category if event else "news")).lower()
        fallback_cat = CATEGORY_TRANSLATIONS.get(cat_key, "ዜና")

        fallback_headline = f"{fallback_cat}፦ {req.headline[:50]}"
        fallback_dek = req.dek or "ዝርዝር መረጃው በመረጋገጥ ላይ ይገኛል።"
        words = fallback_headline.split()
        punchline = [words[0]] if words else ["ዜና"]

        return EditorialTranslationResponse(
            headline=fallback_headline,
            dek=fallback_dek,
            category=fallback_cat,
            punchline_words=punchline,
            slide_headers=[
                fallback_headline,
                "ዋና ዋና ነጥቦች",
                "የተረጋገጡ ዝርዝሮች",
                "ለምን አሳሳቢ ሆነ?",
                "የተረጋገጠ መረጃ",
            ],
            slide_bodies=[
                fallback_dek,
                "• የዜናው ቁልፍ መረጃዎች",
                "በማረጋገጥ ሂደት ላይ የሚገኝ ዝርዝር መረጃ።",
                "ይህ ጉዳይ በቀጣይ ትኩረት የሚሰጠው ይሆናል።",
                "መረጃው በETHIOPIAN TIMES የዜና ማረጋገጫ ክፍል ተረጋግጧል።",
            ],
            translated_language="am",
        )
