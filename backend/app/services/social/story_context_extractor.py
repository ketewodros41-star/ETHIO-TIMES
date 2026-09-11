"""Story context extractor — heuristic-first approach.

Maps news event fields (category, region, title keywords) to a fully
populated StoryContext for FLUX editorial prompt generation.
"""
from __future__ import annotations

import re
from app.models.news_event import NewsEvent
from app.services.social.story_context import StoryContext


# ---------------------------------------------------------------------------
# Location → Landmark lookup
# ---------------------------------------------------------------------------
_LOCATION_LANDMARKS: dict[str, list[str]] = {
    "addis ababa": [
        "Meskel Square", "African Union headquarters", "National Palace",
        "Bole International Airport", "Churchill Avenue", "Holy Trinity Cathedral",
        "Piassa neighborhood", "National Museum of Ethiopia",
    ],
    "addis abeba": [
        "Meskel Square", "National Palace", "Bole International Airport",
    ],
    "tigray": [
        "Gheralta rocky highlands", "Aksum obelisks", "Hawzen plains",
        "Mekele city center",
    ],
    "mekele": [
        "Mekele city center", "Aksum obelisks nearby", "Tigray highlands",
    ],
    "amhara": [
        "Fasil Ghebbi castles of Gondar", "Lake Tana shores", "Blue Nile Falls",
        "Debre Birhan highlands",
    ],
    "gondar": [
        "Fasil Ghebbi Royal Enclosure", "Debre Birhan Selassie church", "Lake Tana",
    ],
    "bahir dar": [
        "Lake Tana shores", "Blue Nile Falls", "Bahir Dar waterfront",
    ],
    "oromia": [
        "coffee highlands", "Awash Valley", "Rift Valley lakes",
    ],
    "jimma": [
        "Jimma coffee highlands", "Gilgel Gibe river area",
    ],
    "somali region": [
        "arid scrubland", "Jijiga marketplace", "nomadic pasturelands",
    ],
    "afar": [
        "Danakil Depression", "Afar salt flats", "Semera city center", "Awash River",
    ],
    "gerd": [
        "Grand Ethiopian Renaissance Dam", "Abbay River gorge", "Blue Nile gorge",
        "GERD reservoir",
    ],
    "blue nile": [
        "Blue Nile Falls", "Abbay River gorge", "Grand Ethiopian Renaissance Dam",
    ],
    # Diaspora
    "minneapolis": [
        "Ethiopian community center", "Minneapolis Ethiopian neighborhood",
        "Ethiopian restaurant storefront",
    ],
    "washington dc": [
        "Ethiopian Embassy", "Washington DC Ethiopian neighborhood",
    ],
    "london": [
        "Ethiopian community gathering", "London Ethiopian cultural center",
    ],
    "dubai": [
        "Ethiopian workers in Gulf setting", "Gulf skyline with Ethiopian community",
    ],
    "riyadh": [
        "Ethiopian workers in Gulf setting",
    ],
}

# ---------------------------------------------------------------------------
# Category → photography specs
# ---------------------------------------------------------------------------
_CATEGORY_SPECS: dict[str, dict] = {
    "politics": {
        "visual_angle": "portrait",
        "camera_lens": "85mm f/1.4",
        "lighting": "dramatic window light",
        "color_grade": "warm editorial",
        "film_stock": "Kodak Portra 400",
        "style_name": "Cinematic Editorial Photography",
        "agency_style": "Reuters editorial photojournalism",
        "subject_type": "political_figure",
    },
    "diplomacy": {
        "visual_angle": "wide_scene",
        "camera_lens": "85mm f/1.4",
        "lighting": "indoor ambient light",
        "color_grade": "neutral editorial",
        "film_stock": "Kodak Portra 400",
        "style_name": "Cinematic Editorial Photography",
        "agency_style": "Reuters editorial photojournalism",
        "subject_type": "political_figure",
    },
    "economy": {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/4",
        "lighting": "soft overcast",
        "color_grade": "clean warm tones",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Premium Editorial Magazine",
        "agency_style": "Bloomberg editorial photography",
        "subject_type": "economic",
    },
    "business": {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/4",
        "lighting": "soft overcast",
        "color_grade": "clean warm tones",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Premium Editorial Magazine",
        "agency_style": "Bloomberg editorial photography",
        "subject_type": "economic",
    },
    "infrastructure": {
        "visual_angle": "architectural",
        "camera_lens": "24mm wide angle",
        "lighting": "golden hour",
        "color_grade": "warm golden tones",
        "film_stock": "Fujifilm Velvia 50",
        "style_name": "Architectural Editorial",
        "agency_style": "Architectural Digest editorial photography",
        "subject_type": "infrastructure",
    },
    "military": {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/5.6",
        "lighting": "harsh flat overcast",
        "color_grade": "desaturated muted",
        "film_stock": "Ilford HP5 black and white grain",
        "style_name": "Documentary-Inspired",
        "agency_style": "AP wire service documentary photojournalism",
        "subject_type": "military",
    },
    "security": {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/5.6",
        "lighting": "harsh flat overcast",
        "color_grade": "desaturated muted",
        "film_stock": "Ilford HP5 black and white grain",
        "style_name": "Documentary-Inspired",
        "agency_style": "AP wire service documentary photojournalism",
        "subject_type": "military",
    },
    "humanitarian": {
        "visual_angle": "wide_scene",
        "camera_lens": "50mm f/2.8",
        "lighting": "overcast grey flat",
        "color_grade": "desaturated documentary",
        "film_stock": "Kodak Tri-X 400 grain",
        "style_name": "Documentary-Inspired",
        "agency_style": "UNICEF humanitarian documentary photography",
        "subject_type": "humanitarian",
    },
    "flood": {
        "visual_angle": "aerial",
        "camera_lens": "24mm wide angle",
        "lighting": "overcast grey flat",
        "color_grade": "desaturated crisis tones",
        "film_stock": "Kodak Tri-X 400 grain",
        "style_name": "Documentary-Inspired",
        "agency_style": "AP wire service documentary photojournalism",
        "subject_type": "humanitarian",
    },
    "culture": {
        "visual_angle": "portrait",
        "camera_lens": "85mm f/2.0",
        "lighting": "warm golden hour",
        "color_grade": "warm rich tones",
        "film_stock": "Kodak Portra 800",
        "style_name": "Cultural Contemporary",
        "agency_style": "National Geographic cultural documentary",
        "subject_type": "cultural",
    },
    "diaspora": {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/2.8",
        "lighting": "ambient urban light",
        "color_grade": "warm neighborhood tones",
        "film_stock": "Fujifilm Superia 400",
        "style_name": "Cultural Contemporary",
        "agency_style": "NYT cultural documentary photography",
        "subject_type": "diaspora",
    },
    "technology": {
        "visual_angle": "architectural",
        "camera_lens": "24mm f/2.8",
        "lighting": "blue hour",
        "color_grade": "teal and orange editorial",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Ethiopian Futurism",
        "agency_style": "Wired magazine editorial photography",
        "subject_type": "technology",
    },
    "election": {
        "visual_angle": "crowd",
        "camera_lens": "35mm f/4",
        "lighting": "bright outdoor daylight",
        "color_grade": "clean documentary",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Documentary-Inspired",
        "agency_style": "Reuters election documentary photojournalism",
        "subject_type": "election",
    },
    "health": {
        "visual_angle": "portrait",
        "camera_lens": "50mm f/1.8",
        "lighting": "soft indoor window light",
        "color_grade": "clean warm tones",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Premium Editorial Magazine",
        "agency_style": "WHO health documentary photography",
        "subject_type": "humanitarian",
    },
    "sports": {
        "visual_angle": "wide_scene",
        "camera_lens": "200mm telephoto",
        "lighting": "bright outdoor daylight",
        "color_grade": "vibrant athletic",
        "film_stock": "Kodak Ektar 100",
        "style_name": "Sports Editorial",
        "agency_style": "Getty Images sports photojournalism",
        "subject_type": "community",
    },
}

# ---------------------------------------------------------------------------
# Keyword → action/mood detector
# ---------------------------------------------------------------------------
_ACTION_PATTERNS: list[tuple[str, str]] = [
    (r"protest|demonstrat|march|rally|riot", "protest"),
    (r"elect|vote|ballot|poll", "election"),
    (r"flood|displace|disaster|drought|famine|relief", "flood"),
    (r"construct|build|dam|infrastructure|road|railway", "construction"),
    (r"summit|diplomatic|visit|sign|agreement|treaty|negotiat", "diplomatic_meeting"),
    (r"press conference|statement|announce|speech|address", "press_conference"),
    (r"arrest|trial|court|sentence|convict", "trial"),
    (r"celebrat|festival|ceremony|holiday|new year|enkutatash", "ceremony"),
    (r"conflict|fighting|military|offensive|attack|clashes", "conflict"),
    (r"economy|gdp|growth|investment|birr|bond|inflation", "economic_briefing"),
    (r"diaspora|community|immigration|migrant|expat", "community_gathering"),
]

_MOOD_PATTERNS: list[tuple[str, str]] = [
    (r"crisis|emergency|disaster|flood|famine|conflict|fighting", "crisis"),
    (r"peace|agreement|celebrat|hopeful|progress|growth", "hopeful"),
    (r"tense|protest|demonstrat|riot|clashes|unrest", "tense"),
    (r"celebrat|festival|ceremony|holiday|win|champion", "celebratory"),
    (r"death|killed|died|funeral|mourning", "somber"),
    (r"urgent|breaking|critical|major|massive", "urgent"),
    (r"diplomatic|summit|negotiat|deal|agreement", "diplomatic"),
]


def _detect_action(text: str) -> str:
    low = text.lower()
    for pattern, action in _ACTION_PATTERNS:
        if re.search(pattern, low):
            return action
    return "press_conference"


def _detect_mood(text: str) -> str:
    low = text.lower()
    for pattern, mood in _MOOD_PATTERNS:
        if re.search(pattern, low):
            return mood
    return "neutral"


def _get_landmarks(location: str | None) -> list[str]:
    if not location:
        return ["Addis Ababa city center", "Ethiopian capital"]
    low = location.lower()
    for key, landmarks in _LOCATION_LANDMARKS.items():
        if key in low:
            return landmarks
    return [f"{location}, Ethiopia"]


def _get_category_specs(category: str | None) -> dict:
    if not category:
        return _CATEGORY_SPECS["economy"]
    low = category.lower()
    # Try direct match
    for key in _CATEGORY_SPECS:
        if key in low:
            return _CATEGORY_SPECS[key]
    # fallback
    return {
        "visual_angle": "wide_scene",
        "camera_lens": "35mm f/4",
        "lighting": "soft natural daylight",
        "color_grade": "neutral editorial",
        "film_stock": "Fujifilm Pro 400H",
        "style_name": "Premium Editorial Magazine",
        "agency_style": "Reuters editorial photojournalism",
        "subject_type": "general",
    }


class StoryContextExtractor:
    """Extracts StoryContext from a NewsEvent using heuristic lookup tables."""

    def extract(self, event: NewsEvent, headline: str, summary: str) -> StoryContext:
        combined_text = f"{headline} {summary} {event.title or ''}"

        # Get category-based specs
        category = event.primary_category
        specs = _get_category_specs(category)

        # Detect action and mood from text
        action = _detect_action(combined_text)
        mood = _detect_mood(combined_text)

        # Get location landmarks
        primary_location = event.primary_region
        landmarks = _get_landmarks(primary_location)

        # Determine named roles based on subject type
        subject_type = specs["subject_type"]
        named_roles = self._get_named_roles(subject_type, action, combined_text)

        return StoryContext(
            headline=headline,
            primary_location=primary_location,
            location_type="city" if primary_location and primary_location.lower() in ["addis ababa", "mekele", "gondar", "bahir dar", "jimma"] else "region",
            country="Ethiopia",
            subject_type=subject_type,
            named_roles=named_roles,
            action=action,
            mood=mood,
            timeframe="ongoing",
            landmark_references=landmarks[:2],  # Use top 2 landmarks
            visual_angle=specs["visual_angle"],
            camera_lens=specs["camera_lens"],
            lighting=specs["lighting"],
            color_grade=specs["color_grade"],
            film_stock=specs["film_stock"],
            style_name=specs["style_name"],
            agency_style=specs["agency_style"],
        )

    def _get_named_roles(
        self, subject_type: str, action: str, text: str
    ) -> list[str]:
        """Return descriptive roles (never real person names) for the image subject."""
        role_map = {
            "political_figure": {
                "diplomatic_meeting": ["an Ethiopian Head of State in formal attire", "a senior African diplomat"],
                "press_conference": ["a senior Ethiopian government official at a podium"],
                "conflict": ["Ethiopian government officials in serious discussion"],
                "election": ["Ethiopian political candidates at a rally"],
                "default": ["a senior Ethiopian government official in formal attire"],
            },
            "military": {
                "conflict": ["Ethiopian military personnel in olive green fatigues"],
                "press_conference": ["Ethiopian military commanders at a briefing podium"],
                "default": ["Ethiopian military personnel in uniform"],
            },
            "humanitarian": {
                "flood": ["displaced Ethiopian families at an emergency shelter"],
                "default": ["Ethiopian humanitarian aid workers and community members"],
            },
            "economic": {
                "economic_briefing": ["Ethiopian financial officials presenting economic data at a conference"],
                "default": ["Ethiopian merchants and businesspeople in a modern setting"],
            },
            "community": {
                "protest": ["a large crowd of Ethiopian demonstrators in an urban setting"],
                "election": ["a long queue of Ethiopian voters outside a polling station"],
                "default": ["Ethiopian community members gathered in an urban setting"],
            },
            "diaspora": {
                "ceremony": ["Ethiopian-American community members in traditional habesha dress"],
                "community_gathering": ["Ethiopian diaspora community members gathered at a community center"],
                "default": ["Ethiopian community members in an urban diaspora setting"],
            },
            "infrastructure": {
                "construction": ["construction workers and engineers on a major Ethiopian infrastructure project"],
                "default": ["a wide view of Ethiopian infrastructure development"],
            },
            "cultural": {
                "ceremony": ["Ethiopian women in traditional colorful habesha kemis dresses at a cultural festival"],
                "default": ["Ethiopian people in traditional dress at a cultural gathering"],
            },
            "technology": {
                "default": ["Ethiopian tech workers at a modern innovation hub in Addis Ababa"],
            },
            "election": {
                "default": ["a long queue of Ethiopian voters outside a polling station"],
            },
        }

        subject_roles = role_map.get(subject_type, {})
        return subject_roles.get(action, subject_roles.get("default", ["Ethiopian people in a news-relevant setting"]))
