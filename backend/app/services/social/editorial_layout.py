"""Authoritative copy budgets for the supported Instagram editorial layouts.

The same limits are returned by the translation endpoint so the Studio can warn
before a preview clips text. Models are asked to respect these budgets, but
the server validates them because provider output is untrusted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


SUPPORTED_AUTOMATION_THEMES = frozenset({"broadcast_impact", "country_spotlight"})
SUPPORTED_CONTENT_MODES = frozenset({"single_card", "carousel_5"})


@dataclass(frozen=True)
class EditorialLayoutBudget:
    headline_max_chars: int
    headline_max_words: int
    dek_max_chars: int
    highlight_max_words: int
    slide_header_max_chars: int | None = None
    slide_body_max_chars: int | None = None
    slide_count: int = 0

    def as_dict(self) -> dict[str, int | None]:
        return asdict(self)


_SINGLE = EditorialLayoutBudget(68, 9, 150, 3)
_CAROUSEL = EditorialLayoutBudget(62, 9, 135, 3, 54, 175, 5)


def normalise_content_mode(template: str | None, content_mode: str | None) -> str:
    """Accept existing Studio values while exposing a stable new contract."""
    if content_mode in SUPPORTED_CONTENT_MODES:
        return content_mode
    return "carousel_5" if template == "carousel" else "single_card"


def get_editorial_layout_budget(
    *, theme: str | None, template: str | None, content_mode: str | None
) -> EditorialLayoutBudget:
    # Both supported themes currently use the same safe copy areas. Keeping the
    # selector here makes later theme-specific budgets additive and explicit.
    mode = normalise_content_mode(template, content_mode)
    return _CAROUSEL if mode == "carousel_5" else _SINGLE
