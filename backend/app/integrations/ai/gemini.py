"""Gemini provider wiring (Phase 1 stub).

The class captures configuration and the intended API shape. Actual calls to
the Gemini / Imagen APIs are deferred to Phase 2. Methods raise
`ProviderNotConfiguredError` when no API key is present and otherwise raise
`NotImplementedError` to make it explicit that the pipeline is not wired yet.
"""

from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import (
    AIProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProvider,
    ProviderNotConfiguredError,
    TextGenerationRequest,
    TextGenerationResult,
)


class GeminiTextProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_text_model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResult:
        if not self.is_available():
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        # Phase 2: call google-generativeai / Vertex AI here.
        raise NotImplementedError(
            "Gemini text generation is wired in Phase 2 (analysis pipeline)."
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.is_available():
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        # Phase 2: call the embeddings endpoint and store on Article.embedding.
        raise NotImplementedError(
            "Gemini embeddings are wired in Phase 2 (semantic clustering)."
        )


class GeminiImageProvider(ImageProvider):
    name = "gemini-imagen"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_image_model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.is_available():
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        # Phase 3+: call Imagen and return bytes for the Visual Director.
        raise NotImplementedError(
            "Image generation is wired in a later phase (Visual Director)."
        )
