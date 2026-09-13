"""Provider registry / factory.

Central place to resolve the active text and image providers. In later phases
this can select among multiple providers based on config or task type.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProvider,
    ImageProvider,
    ProviderResponseError,
    TextGenerationRequest,
    TextGenerationResult,
)
from app.integrations.ai.gemini import GeminiImageProvider, GeminiTextProvider

logger = get_logger(__name__)


class ResilientTranslationProvider(AIProvider):
    """Wraps multiple AI providers in order of preference, cascading on failure."""
    name: str = "resilient-translation-provider"

    def __init__(self, providers: list[AIProvider]) -> None:
        self.providers = [p for p in providers if p is not None and p.is_available()]

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        last_exc: Exception | None = None
        for p in self.providers:
            try:
                return p.generate_json(request)
            except Exception as exc:
                p_name = getattr(p, "name", type(p).__name__)
                logger.warning(
                    "translation_provider_cascade_fallback",
                    failing_provider=p_name,
                    error=str(exc),
                )
                last_exc = exc
                continue
        raise ProviderResponseError(f"All translation providers failed. Last error: {last_exc}")

    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResult:
        last_exc: Exception | None = None
        for p in self.providers:
            if hasattr(p, "generate_text"):
                try:
                    return p.generate_text(request)
                except Exception as exc:
                    p_name = getattr(p, "name", type(p).__name__)
                    logger.warning(
                        "translation_provider_text_cascade_fallback",
                        failing_provider=p_name,
                        error=str(exc),
                    )
                    last_exc = exc
                    continue
        raise ProviderResponseError(f"All translation providers failed. Last error: {last_exc}")

    def embed(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        for p in self.providers:
            try:
                return p.embed(texts, task_type=task_type)
            except Exception:
                continue
        return []


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
    """Resilient translation provider reserved specifically for high-fidelity Amharic translation.
    Prioritizes Gemini (gemini-2.5-flash-lite with multi-model fallback) for blazing fast (<2s),
    high-quota (1,500 req/day) Amharic translations, cascading to AgentRouter and NVIDIA NIM.
    """
    providers: list[AIProvider] = []

    # 1. Gemini (100% Free tier: 1500 Requests/Day, fast 1-2s response, multi-model fallback)
    if settings.gemini_api_key:
        try:
            gemini = GeminiTextProvider()
            if gemini.is_available():
                providers.append(gemini)
        except Exception:
            pass

    # 2. AgentRouter (DeepSeek)
    if getattr(settings, "agent_router_key", None):
        try:
            from app.integrations.ai.agent_router import AgentRouterTextProvider
            ar = AgentRouterTextProvider()
            if ar.is_available():
                providers.append(ar)
        except Exception:
            pass

    # 3. NVIDIA NIM
    if getattr(settings, "nvidia_api_key", None):
        try:
            from app.integrations.ai.nvidia import NvidiaTextProvider
            nvidia = NvidiaTextProvider()
            if nvidia.is_available():
                providers.append(nvidia)
        except Exception:
            pass

    if providers:
        return ResilientTranslationProvider(providers)

    return GeminiTextProvider()


def get_image_provider() -> ImageProvider:
    from app.integrations.ai.flux_image import EditorialImageProvider
    return EditorialImageProvider()
