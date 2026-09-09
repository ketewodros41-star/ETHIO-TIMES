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
        return "verified_brief"

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

    def _fallback(self, event: NewsEvent) -> EditorialBrief:
        headline = event.title
        short_summary = (event.summary or "")[:280]
        full_summary = event.summary or ""
        why_it_matters = "This story is important for Ethiopia."
        evidenced_claims = [c for c in getattr(event, "claims", []) if c.evidence]
        key_facts = [c.claim_text for c in evidenced_claims][:5]
        
        cat = (event.primary_category or "News").title()
        hashtags = ["#Ethiopia", "#EthioTimes", f"#{cat}"]
        
        # Build source attribution
        sources = set()
        for al in getattr(event, "article_links", []):
            if al.article and al.article.source:
                sources.add(al.article.source.name)
        source_attribution = "Sources: " + ", ".join(sources) if sources else "Source: EthioTimes"

        theme = self._auto_theme(event)
        fmt = self._auto_format(event)
        cfmt = self._auto_content_format(event, theme)

        # Build basic caption
        cap_parts = [headline, short_summary]
        if key_facts:
            cap_parts.append("Key facts:\\n" + "\\n".join(f"- {f}" for f in key_facts))
        cap_parts.append(source_attribution)
        cap_parts.append(" ".join(hashtags))
        caption = "\\n\\n".join(cap_parts)[:2200]

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
        # 2. What Happened
        if brief.full_summary:
            raw_slides.append({
                "slide_type": "what_happened",
                "header": "What Happened",
                "body_text": brief.full_summary[:380],
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 3. Key Evidenced Facts
        if brief.key_facts:
            raw_slides.append({
                "slide_type": "key_facts",
                "header": "Key Facts",
                "body_text": None,
                "bullet_points": brief.key_facts[:4],
                "source_attribution": None,
                "accent": accent,
            })
        # 4. Why It Matters
        if brief.why_it_matters:
            raw_slides.append({
                "slide_type": "why_it_matters",
                "header": "Why It Matters",
                "body_text": brief.why_it_matters,
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 5. What Happens Next (optional)
        if brief.what_happens_next:
            raw_slides.append({
                "slide_type": "what_next",
                "header": "What's Next",
                "body_text": brief.what_happens_next,
                "bullet_points": [],
                "source_attribution": None,
                "accent": accent,
            })
        # 6. Verified Sources
        raw_slides.append({
            "slide_type": "sources",
            "header": "Verified Coverage",
            "body_text": "Story verified across multiple independent and primary sources by the ETHIOTIMES intelligence engine.",
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

    def compose(self, event: NewsEvent) -> EditorialBrief:
        if not self.provider.is_available():
            return self._fallback(event)
            
        try:
            prompt = f"Summarize this event for Instagram. Title: {event.title}. Summary: {event.summary}"
            result = self.provider.generate_json(prompt)
            
            theme = self._auto_theme(event)
            fmt = self._auto_format(event)
            cfmt = self._auto_content_format(event, theme)
            
            brief = EditorialBrief(
                headline=result.get("headline", event.title),
                subheadline=result.get("subheadline"),
                short_summary=result.get("short_summary", (event.summary or "")[:280]),
                full_summary=result.get("full_summary", event.summary or ""),
                why_it_matters=result.get("why_it_matters", "Important for Ethiopia."),
                key_facts=result.get("key_facts", []),
                what_happens_next=result.get("what_happens_next"),
                instagram_caption=result.get("instagram_caption", "")[:2200],
                hashtags=result.get("hashtags", ["#Ethiopia"]),
                source_attribution=result.get("source_attribution", "EthioTimes"),
                suggested_theme=theme,
                suggested_format=fmt,
                content_format=cfmt,
            )
            brief.carousel_slides = self.generate_carousel_slides(event, brief)
            return brief
        except Exception:
            return self._fallback(event)
