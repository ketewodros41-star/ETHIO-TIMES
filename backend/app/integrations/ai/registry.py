"""Provider registry / factory.

Central place to resolve the active text and image providers. In later phases
this can select among multiple providers based on config or task type.
"""

from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import AIProvider, ImageProvider
from app.integrations.ai.gemini import GeminiImageProvider, GeminiTextProvider


def get_text_provider() -> AIProvider:
    # 1. AgentRouter (configured via AGENT_ROUTER in .env)
    if getattr(settings, "agent_router_key", None):
        try:
            from app.integrations.ai.agent_router import AgentRouterTextProvider
            ar = AgentRouterTextProvider()
            if ar.is_available():
                return ar
        except Exception:
            pass

    # 2. NVIDIA NIM (configured via NVIDIA_API_KEY in .env)
    if getattr(settings, "nvidia_api_key", None):
        try:
            from app.integrations.ai.nvidia import NvidiaTextProvider
            nvidia = NvidiaTextProvider()
            if nvidia.is_available():
                return nvidia
        except Exception:
            pass

    # 3. Gemini Developer API
    if settings.gemini_api_key:
        try:
            gemini = GeminiTextProvider()
            if gemini.is_available():
                return gemini
        except Exception:
            pass

    return GeminiTextProvider()


def get_image_provider() -> ImageProvider:
    from app.integrations.ai.flux_image import EditorialImageProvider
    return EditorialImageProvider()
