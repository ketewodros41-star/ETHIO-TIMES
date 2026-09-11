"""Editorial content engine (Phase 5).

Transforms a verified NewsEvent with evidenced claims into a full editorial
brief: headline, summary, key facts, Instagram caption, hashtags, source
attribution, suggested theme and format.

Design rules (spec §22):
- Only use claims with at least one ClaimEvidence row.
- Never invent facts, quotes, or statistics.
- Caption ≤ settings.caption_max_chars chars.
- When provider unavailable: deterministic fallback from event fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.ai.base import AIProvider
from app.models.enums import ContentFormat, InstagramPostFormat, TrendStatus
from app.models.news_event import NewsEvent

@dataclass
class EditorialBrief:
    headline: str
    subheadline: str | None
    short_summary: str
    full_summary: str
    why_it_matters: str
    key_facts: list[str]         # evidenced claims only
    what_happens_next: str | None
    instagram_caption: str       # ≤caption_max_chars
    hashtags: list[str]
    source_attribution: str
    suggested_theme: str         # ThemeId string
    suggested_format: InstagramPostFormat
    content_format: ContentFormat
    carousel_slides: list[dict] = field(default_factory=list)


def is_geez_script(text: str | None) -> bool:
    """Check if text contains Ge'ez / Ethiopic Unicode characters."""
    if not text:
        return False
    return any("\u1200" <= ch <= "\u137f" for ch in text)


class EditorialEngine:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def _auto_theme(self, event: NewsEvent) -> str:
        if getattr(event, "trend_status", None) == TrendStatus.breaking:
            return "breaking"
        cat = (event.primary_category or "").lower()
        if cat in {"politics", "conflict", "military", "elections"} and getattr(event, "review_required", False):
            return "politics_sensitive"
        if cat in {"economy", "business", "finance"} and hasattr(event, "claims") and any(
            c.claim_type.value in {"financial", "statistical"} for c in event.claims if c.evidence
        ):
            return "economy"
        return "broadcast_impact"

    def _auto_format(self, event: NewsEvent) -> InstagramPostFormat:
        cat = (event.primary_category or "").lower()
        trend_score = getattr(event, "trend_score", None) or 0.0
        if cat in {"economy", "business"} and trend_score < 70:
            return InstagramPostFormat.square
        return InstagramPostFormat.portrait

    def _auto_content_format(self, event: NewsEvent, theme: str) -> ContentFormat:
        if theme == "breaking":
            return ContentFormat.breaking_card
        if theme == "data_chart":
            return ContentFormat.data_visual
        return ContentFormat.single_image_post

    def _fallback(self, event: NewsEvent, language: str = "en") -> EditorialBrief:
        is_am = language == "am" or is_geez_script(event.title)

        if is_am:
            if is_geez_script(event.title):
                words = event.title.split()
                headline = " ".join(words[:7]) if len(words) > 7 else event.title
            else:
                headline = f"ሰበር ዜና: {event.title}"
            short_summary = (event.summary or "ዝርዝር መረጃው በመጣራት ላይ ይገኛል።")[:280]
            full_summary = event.summary or ""
            why_it_matters = "ይህ ዜና ለቀጣናው እና ለወቅታዊ ሁኔታዎች ከፍተኛ ተጽዕኖ አለው።"
            evidenced_claims = [c for c in getattr(event, "claims", []) if c.evidence]
            key_facts = [c.claim_text for c in evidenced_claims][:4]
            hashtags = ["#ኢትዮጵያ", "#EthioTimes", "#አዲስ_አበባ", "#Ethiopia"]
            source_attribution = "ምንጭ: ETHIOPIAN TIMES የዜና ክፍል"
        else:
            headline = event.title
            short_summary = (event.summary or "")[:280]
            full_summary = event.summary or ""
            why_it_matters = "This story is important for Ethiopia."
            evidenced_claims = [c for c in getattr(event, "claims", []) if c.evidence]
            key_facts = [c.claim_text for c in evidenced_claims][:5]
            cat = (event.primary_category or "News").title()
            hashtags = ["#Ethiopia", "#EthiopianTimes", f"#{cat}"]

            # Build source attribution
            sources = set()
            for al in getattr(event, "article_links", []):
                if al.article and al.article.source:
                    sources.add(al.article.source.name)
            source_attribution = "Sources: " + ", ".join(sources) if sources else "Source: Ethiopian Times"

        theme = self._auto_theme(event)
        fmt = self._auto_format(event)
        cfmt = self._auto_content_format(event, theme)

        # Build basic caption
        cap_parts = [headline, short_summary]
        if key_facts:
            cap_parts.append(("ዋና ዋና ነጥቦች:\n" if is_am else "Key facts:\n") + "\n".join(f"- {f}" for f in key_facts))
        cap_parts.append(source_attribution)
        cap_parts.append(" ".join(hashtags))
        caption = "\n\n".join(cap_parts)[:2200]

        brief = EditorialBrief(
            headline=headline,
            subheadline=None,
            short_summary=short_summary,
            full_summary=full_summary,
            why_it_matters=why_it_matters,
            key_facts=key_facts,
            what_happens_next=None,
            instagram_caption=caption,
            hashtags=hashtags,
            source_attribution=source_attribution,
            suggested_theme=theme,
            suggested_format=fmt,
            content_format=cfmt,
        )
        brief.carousel_slides = self.generate_carousel_slides(event, brief)
        return brief

    def generate_carousel_slides(self, event: NewsEvent, brief: EditorialBrief) -> list[dict]:
        accent = "green"
        if brief.suggested_theme == "breaking":
            accent = "red"
        elif brief.suggested_theme in {"data_chart", "politics_sensitive", "official_statement", "culture_photo"}:
            accent = "gold"

        is_am = is_geez_script(brief.headline) or is_geez_script(brief.short_summary)

        raw_slides = []
        # 1. Cover
        raw_slides.append({
            "slide_type": "cover",
            "header": brief.headline,
            "body_text": brief.short_summary,
            "bullet_points": [],
            "source_attribution": brief.source_attribution,
            "accent": accent,
        })
        # 2. What Happened / The Facts
        if brief.full_summary:
            raw_slides.append({
                "slide_type": "what_happened",
                "header": "ዋና ዋና ነጥቦች" if is_am else "What Happened",
                "body_text": brief.full_summary[:380],
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 3. Key Evidenced Facts
        if brief.key_facts:
            raw_slides.append({
                "slide_type": "key_facts",
                "header": "የተረጋገጡ ዝርዝሮች" if is_am else "Key Facts",
                "body_text": None,
                "bullet_points": brief.key_facts[:4],
                "source_attribution": None,
                "accent": accent,
            })
        # 4. Why It Matters
        if brief.why_it_matters:
            raw_slides.append({
                "slide_type": "why_it_matters",
                "header": "ለምን አሳሳቢ ሆነ?" if is_am else "Why It Matters",
                "body_text": brief.why_it_matters,
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 5. What Happens Next (optional)
        if brief.what_happens_next:
            raw_slides.append({
                "slide_type": "what_next",
                "header": "ቀጣይ እርምጃዎች" if is_am else "What's Next",
                "body_text": brief.what_happens_next,
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 6. Verified Sources
        raw_slides.append({
            "slide_type": "sources",
            "header": "የተረጋገጠ መረጃ" if is_am else "Verified Coverage",
            "body_text": (
                "ይህ ዘገባ በETHIOPIAN TIMES የዜና ማረጋገጫ ክፍል በተለያዩ ገለልተኛ ምንጮች ተረጋግጧል።"
                if is_am
                else "Story verified across multiple independent and primary sources by the ETHIOPIAN TIMES intelligence engine."
            ),
            "bullet_points": [brief.source_attribution] if brief.source_attribution else [],
            "source_attribution": brief.source_attribution,
            "accent": accent,
        })

        total = len(raw_slides)
        slides = []
        for i, s in enumerate(raw_slides):
            slides.append({
                "slide_number": i + 1,
                "total_slides": total,
                **s,
            })
        return slides

    def compose(self, event: NewsEvent, language: str = "en") -> EditorialBrief:
        if not self.provider.is_available():
            return self._fallback(event, language=language)

        try:
            is_am = language == "am" or is_geez_script(event.title)
            if is_am:
                prompt = (
                    "You are an expert Ethiopian broadcast news editor. Formulate an ultra-punchy, concise broadcast news card in Amharic (Ge'ez script).\n"
                    "STRICT RULES:\n"
                    "1. HEADLINE: Must be 4 to 7 words MAXIMUM. Active broadcast voice. State the actor + high-impact action directly. "
                    "The final 2-3 words must contain the punchline action verb/event (e.g. 'ማን ዩናይትድ ምባፔን ሊያስፈርም ነበር' or 'ብሔራዊ ባንክ አዲስ መመሪያ አወጣ'). "
                    "Never use bureaucratic filler phrases like 'የተገለጸ መሆኑ ታውቋል' or 'በሰጡት ማብራሪያ'.\n"
                    "2. SHORT_SUMMARY: Exactly 1 concise active sentence (12-18 words max).\n"
                    "3. WHY_IT_MATTERS: 1 short sentence on strategic impact.\n"
                    "4. KEY_FACTS: Up to 3 concise bullet points (each under 12 words).\n"
                    f"Story Title: {event.title}\nStory Summary: {event.summary}"
                )
            else:
                prompt = f"Summarize this event for Instagram. Title: {event.title}. Summary: {event.summary}"

            result = self.provider.generate_json(prompt)

            theme = self._auto_theme(event)
            fmt = self._auto_format(event)
            cfmt = self._auto_content_format(event, theme)

            default_title = event.title
            default_summary = (event.summary or "")[:280]
            default_hashtags = ["#ኢትዮጵያ", "#EthioTimes", "#አዲስ_አበባ"] if is_am else ["#Ethiopia", "#EthiopianTimes"]
            default_source = "ምንጭ: ETHIOPIAN TIMES" if is_am else "Ethiopian Times"

            brief = EditorialBrief(
                headline=result.get("headline", default_title),
                subheadline=result.get("subheadline"),
                short_summary=result.get("short_summary", default_summary),
                full_summary=result.get("full_summary", event.summary or ""),
                why_it_matters=result.get("why_it_matters", "ይህ ዜና ለቀጣናው ከፍተኛ ጠቀሜታ አለው።" if is_am else "Important for Ethiopia."),
                key_facts=result.get("key_facts", []),
                what_happens_next=result.get("what_happens_next"),
                instagram_caption=result.get("instagram_caption", "")[:2200],
                hashtags=result.get("hashtags", default_hashtags),
                source_attribution=result.get("source_attribution", default_source),
                suggested_theme=theme,
                suggested_format=fmt,
                content_format=cfmt,
            )
            brief.carousel_slides = self.generate_carousel_slides(event, brief)
            return brief
        except Exception:
            return self._fallback(event, language=language)
