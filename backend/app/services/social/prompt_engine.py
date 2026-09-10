"""FLUX-optimized editorial prompt engine for ETHIOTIMES.

Builds photojournalism-quality image prompts based on extracted story context.
Researched approach mirrors AP, Reuters, NYT editorial photography standards.
FLUX (via T5-XXL encoder) responds best to natural language sentences,
camera/lens references, film stock names, and spatial composition descriptions.
"""
from __future__ import annotations

from app.models.news_event import NewsEvent
from app.services.social.story_context import StoryContext
from app.services.social.visual_director import VisualStrategy


# ---------------------------------------------------------------------------
# Visual angle → opening scene direction
# ---------------------------------------------------------------------------
_ANGLE_DIRECTION: dict[str, str] = {
    "portrait": "A close-up editorial portrait",
    "wide_scene": "A wide editorial scene",
    "aerial": "An aerial wide-angle photograph",
    "symbolic": "A symbolic editorial photograph",
    "architectural": "An architectural editorial photograph",
    "crowd": "A wide documentary crowd photograph",
    "close_up": "An intimate close-up editorial photograph",
}

# Mood → lighting and atmosphere
_MOOD_ATMOSPHERE: dict[str, str] = {
    "crisis": "Heavy overcast sky, flat grey light, tense and urgent atmosphere",
    "hopeful": "Soft golden late-afternoon light, optimistic and forward-looking atmosphere",
    "tense": "Dramatic high-contrast lighting, tense and charged atmosphere",
    "celebratory": "Warm golden sunlight, joyful and vibrant celebratory atmosphere",
    "neutral": "Soft natural daylight, neutral informative atmosphere",
    "somber": "Muted overcast light, somber and reflective atmosphere",
    "urgent": "Harsh overhead light, urgent breaking-news atmosphere",
    "diplomatic": "Warm indoor ambient light from tall windows, formal authoritative atmosphere",
}


class PromptEngine:
    """Builds FLUX-optimized editorial image prompts from story context."""

    def build_prompt(
        self,
        strategy: VisualStrategy,
        event: NewsEvent,
        story_context: StoryContext | None = None,
    ) -> str:
        # If we have rich story context, use the full contextual builder
        if story_context is not None:
            return self._build_contextual_prompt(strategy, story_context)
        # Fallback to strategy-only prompt
        return self._build_strategy_prompt(strategy, event)

    def _build_contextual_prompt(
        self, strategy: VisualStrategy, ctx: StoryContext
    ) -> str:
        """Build a rich, story-specific FLUX prompt.

        Structure (FLUX-optimized — front-load subject, then setting, then tech):
        [Subject+Action], [Location/Landmark], [Lighting], [Mood], [Camera gear],
        [Film stock/color grade], [Composition], [Style/agency], [Quality anchors]
        """
        parts: list[str] = []

        # --- 1. Opening angle direction + subject ---
        angle_dir = _ANGLE_DIRECTION.get(ctx.visual_angle, "A wide editorial scene")
        if ctx.named_roles:
            subject_desc = ctx.named_roles[0]
        else:
            subject_desc = f"Ethiopian people in a {ctx.action.replace('_', ' ')} setting"

        # Build the action phrase
        action_phrase = self._action_phrase(ctx.action, ctx.subject_type)
        parts.append(f"{angle_dir} of {subject_desc} {action_phrase}")

        # --- 2. Location + landmark ---
        if ctx.landmark_references:
            landmark = ctx.landmark_references[0]
            location_str = ctx.primary_location or "Ethiopia"
            parts.append(f"at {landmark}, {location_str}, Ethiopia")
        elif ctx.primary_location:
            parts.append(f"in {ctx.primary_location}, Ethiopia")
        else:
            parts.append("in Ethiopia")

        # --- 3. Setting detail (second landmark as background context) ---
        if len(ctx.landmark_references) > 1:
            parts.append(
                f"{ctx.landmark_references[1]} visible in the background"
            )

        # --- 4. Lighting + mood ---
        atm = _MOOD_ATMOSPHERE.get(ctx.mood, "soft natural daylight, neutral atmosphere")
        parts.append(atm)

        # --- 5. Camera gear (critical for removing plastic AI look) ---
        parts.append(
            f"Shot on Sony A7R V with {ctx.camera_lens} lens"
        )

        # --- 6. Film stock / color grade ---
        parts.append(f"{ctx.film_stock} color grade")

        # --- 7. Composition guidance ---
        comp = self._composition_for_angle(ctx.visual_angle)
        parts.append(comp)

        # --- 8. Style anchor ---
        parts.append(f"{ctx.style_name}, {ctx.agency_style} quality")

        # --- 9. Quality anchors (FLUX-specific — avoid 'hyperrealistic') ---
        parts.append(
            "Photorealistic, authentic skin texture, natural imperfections, "
            "candid editorial photography quality"
        )

        # --- 10. What NOT to show (described positively for FLUX) ---
        parts.append(
            "Clean composition with no visible text, no logos, no watermarks, "
            "no recognizable real faces of living public figures, "
            "no artificial studio lighting, no generic stock photo appearance"
        )

        return ". ".join(parts) + "."

    def _build_strategy_prompt(self, strategy: VisualStrategy, event: NewsEvent) -> str:
        """Fallback when no StoryContext is available."""
        parts = [
            f"An editorial photograph representing {strategy.main_subject}",
            f"{strategy.setting.capitalize()} setting, {strategy.mood} atmosphere",
            f"Visual concept: {strategy.visual_metaphor}",
            f"Composition: {strategy.composition}",
            f"Shot on Sony A7R V, 50mm f/2.8, Fujifilm Pro 400H color grade",
            f"Soft natural daylight, {strategy.style} editorial style",
            "Photorealistic, candid editorial photography, Reuters quality",
            "No text, no logos, no watermarks, no studio lighting",
        ]
        if strategy.cultural_context:
            parts.insert(2, f"Cultural context: {strategy.cultural_context}")
        return ". ".join(parts) + "."

    def _action_phrase(self, action: str, subject_type: str) -> str:
        """Return a natural-language action phrase."""
        phrases = {
            "press_conference": "addressing reporters at a formal press conference podium",
            "diplomatic_meeting": "engaged in a formal diplomatic meeting and handshake",
            "protest": "participating in a peaceful street demonstration, holding signs",
            "election": "standing in line at a polling station, waiting to cast their vote",
            "flood": "surveying flooded landscape from an elevated vantage point",
            "construction": "overseeing construction workers at a major infrastructure site",
            "ceremony": "participating in a traditional Ethiopian cultural ceremony",
            "community_gathering": "gathered at a community event, engaged in conversation",
            "conflict": "in a tense operational situation in a field setting",
            "economic_briefing": "presenting economic data charts at a formal government briefing",
            "trial": "present at formal court proceedings in a judicial building",
        }
        return phrases.get(action, "in a relevant editorial setting")

    def _composition_for_angle(self, angle: str) -> str:
        """Return composition guidance for the visual angle."""
        compositions = {
            "portrait": "Subject centered, shallow depth of field with softly blurred background, sharp eyes and face, three-quarter view",
            "wide_scene": "Subject in midground, environmental context visible, deep depth of field showing full scene",
            "aerial": "Bird's-eye top-down or high-angle view, full landscape visible, foreground detail with vast background",
            "symbolic": "Strong foreground symbolic element, subject behind, layered composition with visual metaphor",
            "architectural": "Wide-angle with strong leading lines, structure fills frame, human figure for scale in foreground",
            "crowd": "Wide documentary frame, dense crowd in foreground, cityscape or significant building behind",
            "close_up": "Tight framing on face and hands, blurred background, intimate photojournalism style",
        }
        return compositions.get(angle, "Well-composed editorial framing with clear subject and contextual background")
