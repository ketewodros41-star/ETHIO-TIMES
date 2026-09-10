"""Story context dataclass for editorial image direction.

Extracted from a news event before image prompt generation to produce
hyper-specific, story-matched image prompts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StoryContext:
    """Semantic story metadata used to direct editorial image generation."""

    headline: str
    primary_location: str | None = None       # "Addis Ababa", "Minneapolis"
    location_type: str = "city"               # city | region | country | diaspora
    country: str = "Ethiopia"

    # Story subject
    subject_type: str = "general"             # political_figure | community | infrastructure
                                               # military | humanitarian | cultural | economic
                                               # diaspora | election | trial | technology

    # Named roles (never real names — use roles/titles)
    named_roles: list[str] = field(default_factory=list)  # ["Prime Minister", "foreign envoy"]

    # Narrative elements
    action: str = "press_conference"          # press_conference | protest | construction
                                               # flood | ceremony | election | trial
                                               # meeting | celebration | migration | conflict
    mood: str = "neutral"                     # crisis | hopeful | tense | celebratory
                                               # neutral | somber | urgent | diplomatic
    timeframe: str = "ongoing"                # breaking | ongoing | historical

    # Visual specificity
    landmark_references: list[str] = field(default_factory=list)  # ["Meskel Square", ...]
    visual_angle: str = "wide_scene"          # portrait | wide_scene | aerial | symbolic
                                               # architectural | crowd | close_up

    # Photography technical spec
    camera_lens: str = "50mm f/2.8"           # 85mm f/1.4 | 35mm f/4 | 24mm wide | etc.
    lighting: str = "soft overcast"           # golden_hour | overcast | dramatic_window
                                               # harsh_midday | indoor_ambient | blue_hour
    color_grade: str = "neutral editorial"    # warm_documentary | cool_urgent
                                               # desaturated_crisis | clean_warm | teal_orange
    film_stock: str = "Fujifilm Pro 400H"     # Kodak Portra 400 | Ilford HP5 | Fujifilm

    # Photography style
    style_name: str = "Premium Editorial Magazine"
    agency_style: str = "Reuters editorial photojournalism"  # Reuters | AP | NYT | Bloomberg
