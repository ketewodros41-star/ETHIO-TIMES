"""Visual Director agent (Phase 5, spec §26) — Phase 7 enhanced with StoryContext."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, TextGenerationRequest
from app.models.news_event import NewsEvent
from app.services.social.story_context import StoryContext
from app.services.social.story_context_extractor import StoryContextExtractor

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

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
        """Produce a VisualStrategy enriched with StoryContext and LLM reasoning."""
        ctx = self.extractor.extract(event, headline, summary)

        # If LLM provider (e.g. AgentRouter / deepseek-v4-flash) is available, use it to direct the shot
        if self.provider and self.provider.is_available():
            try:
                llm_strategy = self._direct_with_llm(event, headline, summary, ctx)
                if llm_strategy:
                    logger.info("visual_director_llm_success", provider=self.provider.name, subject=llm_strategy.main_subject[:60])
                    return llm_strategy
            except Exception as exc:
                logger.warning("visual_director_llm_failed_fallback", error=str(exc))

        return self._strategy_from_context(ctx, event)

    def _direct_with_llm(
        self, event: NewsEvent, headline: str, summary: str, ctx: StoryContext
    ) -> VisualStrategy | None:
        """Use the AI provider (AgentRouter / deepseek-v4-flash) to direct the editorial visual."""
        system = (
            "You are the senior visual photojournalism director for ETHIOTIMES. "
            "Your role is to direct the photographic composition for a real Ethiopian news story. "
            "Guidelines:\n"
            "- Authenticity: Accurately reflect real contemporary Ethiopia (geography, architecture, authentic attire).\n"
            "- Specificity: Specify exact camera gear (e.g. 85mm f/1.4 portrait or 24mm wide angle, natural lighting, documentary style).\n"
            "- Avoid stereotypes: No generic 'African' clichés, no watermarks, no artificial text inside image.\n"
            "Return a JSON object conforming strictly to the requested schema."
        )

        prompt = (
            f"Story Headline: {headline}\n"
            f"Story Summary: {summary}\n"
            f"Location: {ctx.primary_location or event.primary_region or 'Ethiopia'}\n"
            f"Category: {event.primary_category or 'News'}\n"
            f"Detected Figure: {ctx.named_roles[0] if ctx.named_roles else 'None'}\n\n"
            "Direct the visual concept for an editorial photojournalism shot (1080x1350 portrait)."
        )

        schema = {
            "type": "object",
            "properties": {
                "main_subject": {"type": "string", "description": "Specific focal subject or figure (e.g. Ethiopian logistics engineer in safety vest, senior diplomat at podium)"},
                "setting": {"type": "string", "description": "Specific Ethiopian location and physical background environment"},
                "mood": {"type": "string", "description": "Lighting and emotional atmosphere (e.g. focused golden hour, solemn determination)"},
                "composition": {"type": "string", "description": "Camera framing, lens angle, and depth of field (e.g. 35mm wide shot with low angle, sharp foreground)"},
                "visual_metaphor": {"type": "string", "description": "Underlying conceptual metaphor of the story"},
                "style": {"type": "string", "description": "Photographic editorial style (e.g. AP photojournalism, documentary editorial)"},
                "cultural_context": {"type": "string", "description": "Authentic Ethiopian details (contemporary Addis Ababa architecture, Rift Valley landscape)"}
            },
            "required": ["main_subject", "setting", "mood", "composition", "style"]
        }

        req = TextGenerationRequest(
            prompt=prompt,
            system=system,
            response_schema=schema,
            max_tokens=512,
            temperature=0.2,
        )
        data = self.provider.generate_json(req)
        if isinstance(data, dict) and data.get("main_subject"):
            return VisualStrategy(
                visual_strategy=data.get("composition", ctx.visual_angle),
                main_subject=data["main_subject"],
                setting=data.get("setting", f"{ctx.primary_location or 'Ethiopia'}"),
                mood=data.get("mood", ctx.mood),
                composition=data.get("composition", ctx.visual_angle),
                visual_metaphor=data.get("visual_metaphor", f"Ethiopian {event.primary_category} story"),
                style=data.get("style", ctx.style_name),
                cultural_context=data.get("cultural_context", f"Contemporary Ethiopian context, {ctx.primary_location}"),
                negative_constraints=list(_ALWAYS_BLOCKED),
                story_context=ctx,
            )
        return None

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
