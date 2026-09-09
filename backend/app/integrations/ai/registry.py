"""Provider registry / factory.

Central place to resolve the active text and image providers. In later phases
this can select among multiple providers based on config or task type.
"""

from __future__ import annotations

from app.integrations.ai.base import AIProvider, ImageProvider
from app.integrations.ai.gemini import GeminiImageProvider, GeminiTextProvider


def get_text_provider() -> AIProvider:
    return GeminiTextProvider()


def get_image_provider() -> ImageProvider:
    return GeminiImageProvider()
