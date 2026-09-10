"""Provider registry / factory.

Central place to resolve the active text and image providers. In later phases
this can select among multiple providers based on config or task type.
"""

from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import AIProvider, ImageProvider
from app.integrations.ai.gemini import GeminiImageProvider, GeminiTextProvider


def get_text_provider() -> AIProvider:
    if settings.gemini_api_key:
        try:
            gemini = GeminiTextProvider()
            if gemini.is_available():
                return gemini
        except Exception:
            pass

    if settings.nvidia_api_key:
        try:
            from app.integrations.ai.nvidia import NvidiaTextProvider
            nvidia = NvidiaTextProvider()
            if nvidia.is_available():
                return nvidia
        except Exception:
            pass

    return GeminiTextProvider()


def get_image_provider() -> ImageProvider:
    from app.integrations.ai.flux_image import EditorialImageProvider
    return EditorialImageProvider()
