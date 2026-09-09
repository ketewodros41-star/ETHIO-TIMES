"""Prompt templates and JSON response schemas for the intelligence steps.

Response schemas are plain JSON-schema dicts passed to the Gemini provider as
``response_schema`` so the model is constrained to emit parseable JSON matching
our Pydantic contracts.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Relevance
# --------------------------------------------------------------------------- #
RELEVANCE_SYSTEM = (
    "You are an editor for ETHIOTIMES, an Ethiopian news intelligence desk. "
    "Decide whether a news item is meaningfully about Ethiopia (its people, "
    "government, economy, regions, diaspora, or events with direct Ethiopian "
    "impact). Mentions in passing do not count. Respond ONLY with JSON."
)

RELEVANCE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "is_ethiopia_related": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "primary_region": {"type": "string", "nullable": True},
        "reason": {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_ethiopia_related", "score", "reason", "categories"],
}


def relevance_prompt(title: str | None, summary: str | None, content: str | None) -> str:
    body = _join_fields(title, summary, content)
    return (
        "Assess the Ethiopia relevance of the following news item.\n"
        "Return JSON with: is_ethiopia_related (bool), score (0-100 confidence "
        "that it is Ethiopia-related), primary_region (Ethiopian region/city or "
        "null), reason (one sentence), categories (list of high-level topics).\n\n"
        f"{body}"
    )


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
ANALYSIS_SYSTEM = (
    "You are a multilingual news analyst for ETHIOTIMES. You analyze articles in "
    "English, Amharic, and Afaan Oromo (and other languages). Extract structured "
    "facts precisely and neutrally. Respond ONLY with JSON."
)

ANALYSIS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "language": {"type": "string"},
        "language_name": {"type": "string", "nullable": True},
        "category": {"type": "string"},
        "subcategory": {"type": "string", "nullable": True},
        "entities": {
            "type": "object",
            "properties": {
                "people": {"type": "array", "items": {"type": "string"}},
                "organizations": {"type": "array", "items": {"type": "string"}},
                "companies": {"type": "array", "items": {"type": "string"}},
                "government_institutions": {"type": "array", "items": {"type": "string"}},
                "countries": {"type": "array", "items": {"type": "string"}},
                "regions": {"type": "array", "items": {"type": "string"}},
                "cities": {"type": "array", "items": {"type": "string"}},
            },
        },
        "dates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "iso": {"type": "string", "nullable": True},
                    "context": {"type": "string", "nullable": True},
                },
                "required": ["text"],
            },
        },
        "money": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "string"},
                    "currency": {"type": "string", "nullable": True},
                    "context": {"type": "string", "nullable": True},
                },
                "required": ["amount"],
            },
        },
        "statistics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "unit": {"type": "string", "nullable": True},
                    "context": {"type": "string", "nullable": True},
                },
                "required": ["value"],
            },
        },
        "topics": {"type": "array", "items": {"type": "string"}},
        "importance": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string", "nullable": True},
    },
    "required": ["language", "category", "entities", "topics", "importance"],
}


def analysis_prompt(title: str | None, summary: str | None, content: str | None) -> str:
    body = _join_fields(title, summary, content)
    return (
        "Analyze the following news article and return JSON with: language (ISO "
        "code), language_name, category, subcategory, entities (people, "
        "organizations, companies, government_institutions, countries, regions, "
        "cities), dates, money, statistics, topics, importance (0-100 editorial "
        "importance), and a neutral one-paragraph summary.\n\n"
        f"{body}"
    )


# --------------------------------------------------------------------------- #
# Clustering confirmation (borderline pairs only)
# --------------------------------------------------------------------------- #
CLUSTER_SYSTEM = (
    "You determine whether two news items describe the SAME real-world event. "
    "Cross-language coverage of one event should be treated as the same event. "
    "Respond ONLY with JSON."
)

CLUSTER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "relation": {
            "type": "string",
            "enum": ["duplicate", "same_event", "related", "unrelated"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["relation", "confidence"],
}


def cluster_prompt(a: dict, b: dict) -> str:
    return (
        "Do these two news items describe the same real-world event?\n"
        "Return JSON: relation (duplicate|same_event|related|unrelated), "
        "confidence (0-1), reason.\n\n"
        f"ITEM A:\nTitle: {a.get('title')}\nSummary: {a.get('summary')}\n\n"
        f"ITEM B:\nTitle: {b.get('title')}\nSummary: {b.get('summary')}"
    )


# --------------------------------------------------------------------------- #
# Claim extraction (Phase 3)
# --------------------------------------------------------------------------- #
CLAIM_SYSTEM = (
    "You are a verification editor for ETHIOTIMES. Extract discrete, checkable "
    "claims from Ethiopian news coverage. Be precise and neutral. Do not invent "
    "facts that are not in the text. Respond ONLY with JSON."
)

CLAIM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": [
                            "financial",
                            "statistical",
                            "political",
                            "policy",
                            "casualty",
                            "geographic",
                            "timeline",
                            "announcement",
                        ],
                    },
                    "normalized_value": {"type": "string", "nullable": True},
                    "entities": {"type": "array", "items": {"type": "string"}},
                    "excerpt": {"type": "string"},
                    "is_major": {"type": "boolean"},
                    "confidence": {"type": "number"},
                },
                "required": ["claim_text", "claim_type", "excerpt"],
            },
        },
        "cited_institutions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["claims", "cited_institutions"],
}


def claim_extraction_prompt(
    title: str | None, summary: str | None, content: str | None
) -> str:
    body = _join_fields(title, summary, content)
    return (
        "Extract structured claims from the following news article.\n"
        "Return JSON with:\n"
        "- claims: list of {claim_text, claim_type (financial|statistical|"
        "political|policy|casualty|geographic|timeline|announcement), "
        "normalized_value (the key number/date/place if any), entities, "
        "excerpt (verbatim supporting snippet from the article), is_major "
        "(true for material facts), confidence (0-1)}\n"
        "- cited_institutions: official bodies cited as the origin of a fact "
        "(e.g. National Bank of Ethiopia, Ministry of Finance, PMO).\n"
        "Only include claims that are actually stated. Prefer major factual "
        "claims over colour/opinion.\n\n"
        f"{body}"
    )


# --------------------------------------------------------------------------- #
# Contradiction detection (Phase 3)
# --------------------------------------------------------------------------- #
CONTRADICTION_SYSTEM = (
    "You compare claims from different sources covering the SAME event and "
    "identify genuine contradictions (not mere differences in wording or "
    "emphasis). Casualty counts, financial figures, dates, locations, and "
    "who-did-what that cannot all be true are contradictions. Respond ONLY "
    "with JSON."
)

CONTRADICTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_a_index": {"type": "integer"},
                    "claim_b_index": {"type": "integer"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                },
                "required": ["claim_a_index", "claim_b_index", "description", "severity"],
            },
        }
    },
    "required": ["contradictions"],
}


def contradiction_prompt(claims: list[dict]) -> str:
    lines = []
    for i, c in enumerate(claims):
        lines.append(
            f"[{i}] type={c.get('claim_type')} value={c.get('normalized_value')!r} "
            f"entities={c.get('entities')} :: {c.get('claim_text')}"
        )
    listing = "\n".join(lines) if lines else "(no claims)"
    return (
        "Identify pairs of claims that contradict each other.\n"
        "Return JSON: contradictions = list of {claim_a_index, claim_b_index, "
        "description, severity (low|medium|high|critical)}.\n"
        "Severity guide: critical = casualty/death toll or public-safety facts "
        "that cannot both be true; high = material financial/policy numbers or "
        "who-holds-office; medium = dates/places/secondary figures; low = "
        "emphasis or weakly conflicting wording.\n"
        "Use the integer indexes shown. Skip near-duplicates that agree.\n\n"
        f"CLAIMS:\n{listing}"
    )


def _join_fields(title: str | None, summary: str | None, content: str | None) -> str:
    parts = []
    if title:
        parts.append(f"TITLE: {title}")
    if summary:
        parts.append(f"SUMMARY: {summary}")
    if content:
        # Cap content to keep token usage and cost bounded.
        parts.append(f"CONTENT: {content[:6000]}")
    return "\n".join(parts) if parts else "(no text)"
