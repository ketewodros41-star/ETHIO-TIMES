"""Visual Director agent (Phase 5, spec §26)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.ai.base import AIProvider
from app.models.news_event import NewsEvent

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

class VisualDirector:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def _fallback_strategy(self, event: NewsEvent) -> VisualStrategy:
        cat = (event.primary_category or "general").lower()
        style_map = {
            "economy": "Data-Inspired Visual",
            "politics": "Cinematic Editorial Photography",
            "business": "Premium Editorial Magazine",
            "technology": "Ethiopian Futurism",
            "culture": "Cultural Contemporary",
        }
        return VisualStrategy(
            visual_strategy="cinematic_editorial",
            main_subject=event.title,
            setting="contemporary Ethiopia",
            mood="sophisticated and informative",
            composition="central subject with clean negative space, professional lighting",
            visual_metaphor=f"Ethiopian {cat} landscape representing change and progress",
            style=style_map.get(cat, "Premium Editorial Magazine"),
            cultural_context="contemporary urban Ethiopia when relevant" if getattr(event, "primary_region", "") else "",
            negative_constraints=list(_ALWAYS_BLOCKED),
        )

    def direct(self, event: NewsEvent, headline: str, summary: str) -> VisualStrategy:
        if not self.provider.is_available():
            return self._fallback_strategy(event)
        try:
            res = self.provider.generate_json("Generate visual strategy for: " + headline)
            return VisualStrategy(
                visual_strategy=res.get("visual_strategy", "standard"),
                main_subject=res.get("main_subject", headline),
                setting=res.get("setting", "Ethiopia"),
                mood=res.get("mood", "neutral"),
                composition=res.get("composition", "clean"),
                visual_metaphor=res.get("visual_metaphor", "none"),
                style=res.get("style", "Documentary-Inspired"),
                cultural_context=res.get("cultural_context", ""),
                negative_constraints=list(_ALWAYS_BLOCKED) + res.get("negative_constraints", []),
            )
        except Exception:
            return self._fallback_strategy(event)
