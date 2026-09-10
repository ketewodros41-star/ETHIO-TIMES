"""Visual Director agent (Phase 5, spec §26) — Phase 7 enhanced with StoryContext."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.integrations.ai.base import AIProvider
from app.models.news_event import NewsEvent
from app.services.social.story_context import StoryContext
from app.services.social.story_context_extractor import StoryContextExtractor

if TYPE_CHECKING:
    pass

VISUAL_STYLES = [
    "Cinematic Editorial Photography",
    "Ethiopian Futurism",
    "Premium Editorial Magazine",
    "Documentary-Inspired",
    "Conceptual Editorial Art",
    "Architectural Editorial",
    "Data-Inspired Visual",
    "Cultural Contemporary",
]

_ALWAYS_BLOCKED = [
    "generic African imagery",
    "stock photography appearance",
    "fake politicians",
    "text inside image",
    "logos",
    "watermarks",
    "unrelated flags",
    "random traditional clothing",
    "tribal stereotypes",
]


@dataclass
class VisualStrategy:
    visual_strategy: str
    main_subject: str
    setting: str
    mood: str
    composition: str
    visual_metaphor: str
    style: str
    cultural_context: str
    negative_constraints: list[str] = field(default_factory=list)
    story_context: StoryContext | None = None


class VisualDirector:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider
        self.extractor = StoryContextExtractor()

    def direct(self, event: NewsEvent, headline: str, summary: str) -> VisualStrategy:
        """Produce a VisualStrategy enriched with StoryContext."""
        ctx = self.extractor.extract(event, headline, summary)
        return self._strategy_from_context(ctx, event)

    def _strategy_from_context(self, ctx: StoryContext, event: NewsEvent) -> VisualStrategy:
        """Build VisualStrategy directly from StoryContext."""
        landmark = ctx.landmark_references[0] if ctx.landmark_references else "Ethiopia"
        setting = f"{ctx.primary_location or 'Ethiopia'} — {landmark}"

        return VisualStrategy(
            visual_strategy=ctx.visual_angle,
            main_subject=ctx.named_roles[0] if ctx.named_roles else event.title,
            setting=setting,
            mood=ctx.mood,
            composition=ctx.visual_angle,
            visual_metaphor=f"Ethiopian {(event.primary_category or 'news').lower()} story",
            style=ctx.style_name,
            cultural_context=(
                f"Contemporary Ethiopian context, {ctx.primary_location}" if ctx.primary_location else ""
            ),
            negative_constraints=list(_ALWAYS_BLOCKED),
            story_context=ctx,
        )
