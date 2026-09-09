"""Prompt Engine (Phase 5, spec §29)."""
from __future__ import annotations

from app.models.news_event import NewsEvent
from app.services.social.visual_director import VisualStrategy

class PromptEngine:
    def build_prompt(self, strategy: VisualStrategy, event: NewsEvent) -> str:
        parts = [
            f"Create a sophisticated {strategy.style.lower()} image representing {strategy.main_subject}.",
            f"{strategy.setting.capitalize()} environment, {strategy.mood}.",
            f"Visual concept: {strategy.visual_metaphor}.",
            f"Composition: {strategy.composition}.",
            "Dramatic yet natural lighting, atmospheric depth.",
            f"Style: {strategy.style}, premium international editorial quality.",
        ]
        if strategy.cultural_context:
            parts.append(f"Cultural context: {strategy.cultural_context}.")
        parts.append("Photorealistic quality, professional photography aesthetic.")
        neg = ", ".join(strategy.negative_constraints)
        parts.append(f"Avoid: {neg}.")
        return " ".join(parts)
