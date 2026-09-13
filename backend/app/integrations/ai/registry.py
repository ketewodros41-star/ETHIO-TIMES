"""Provider registry / factory.

Central place to resolve the active text and image providers. In later phases
this can select among multiple providers based on config or task type.
"""

from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import AIProvider, ImageProvider
from app.integrations.ai.gemini import GeminiImageProvider, GeminiTextProvider


def get_text_provider() -> AIProvider:
    """General text provider for background pipeline tasks (clustering, relevance, entities).
    Prioritizes free-tier Gemini / Nvidia to conserve AgentRouter tokens.
    """
    # 1. Gemini Developer API (100% Free tier: 15 RPM, 1500 Requests/Day)
    if settings.gemini_api_key:
        try:
            gemini = GeminiTextProvider()
            if gemini.is_available():
                return gemini
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

    # 3. AgentRouter only as last resort if no free provider is configured
    if getattr(settings, "agent_router_key", None):
        try:
            from app.integrations.ai.agent_router import AgentRouterTextProvider
            ar = AgentRouterTextProvider()
            if ar.is_available():
                return ar
        except Exception:
            pass

    return GeminiTextProvider()


def get_translation_provider() -> AIProvider:
    """Specialized provider reserved specifically for high-fidelity Amharic translation.
    Uses AgentRouter (DeepSeek) to ensure top-quality Amharic editorial translation
    while strictly limiting calls to actual Telegram publication events (3-5 calls/day).
    """
    # 1. AgentRouter (DeepSeek) for natural Amharic translation
    if getattr(settings, "agent_router_key", None):
        try:
            from app.integrations.ai.agent_router import AgentRouterTextProvider
            ar = AgentRouterTextProvider()
            if ar.is_available():
                return ar
        except Exception:
            pass

    # 2. Fallback to Gemini if AgentRouter key is exhausted or missing
    return get_text_provider()


def get_image_provider() -> ImageProvider:
    from app.integrations.ai.flux_image import EditorialImageProvider
    return EditorialImageProvider()
