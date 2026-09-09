"""Gemini provider implementation (Phase 2).

Implements structured-JSON text generation and text embeddings behind the
``AIProvider`` interface using the unified ``google-genai`` SDK.

Key behaviors:
- **Structured JSON only**: generation uses ``response_mime_type=application/json``
  with an optional ``response_schema`` so the model returns parseable JSON.
- **Embeddings**: ``gemini-embedding-001`` at a configurable ``output_dimensionality``
  (default 1536). Truncated dims are **not** auto-normalized by this model, so we
  L2-normalize vectors here to keep cosine similarity meaningful.
- **Resilience**: configurable timeout, bounded retries with exponential backoff,
  and explicit mapping of quota/rate-limit (HTTP 429) to ``RateLimitError``.
- **No secret exposure**: the API key is read from settings and never logged.

The SDK is imported lazily so importing this module (and the app) never requires
the dependency to be installed unless a provider is actually constructed/used.
"""

from __future__ import annotations

import json
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProvider,
    ProviderNotConfiguredError,
    ProviderResponseError,
    RateLimitError,
    TextGenerationRequest,
)

logger = get_logger(__name__)


def _l2_normalize(vector: list[float]) -> list[float]:
    """Return the L2-normalized vector (unit length); passthrough if zero."""
    norm = sum(v * v for v in vector) ** 0.5
    if norm <= 0:
        return vector
    return [v / norm for v in vector]


def _is_rate_limit(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "429" in text
        or "resource_exhausted" in text
        or "rate limit" in text
        or "quota" in text
    )


_DEFAULT_KEY = object()


class GeminiTextProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = _DEFAULT_KEY,
        model: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.api_key = settings.gemini_api_key if api_key is _DEFAULT_KEY else api_key
        self.model = model or settings.gemini_text_model
        self.embedding_model = embedding_model or settings.gemini_embedding_model
        self.embedding_dim = settings.embedding_dim
        self._client: Any | None = None

    # -- client ------------------------------------------------------------- #
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> Any:
        if not self.is_available():
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        if self._client is None:
            from google import genai  # lazy import
            from google.genai import types  # noqa: F401

            self._client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": settings.gemini_request_timeout_seconds * 1000},
            )
        return self._client

    def _retryer(self):
        return retry(
            reraise=True,
            stop=stop_after_attempt(settings.gemini_max_retries),
            wait=wait_exponential(
                multiplier=settings.gemini_retry_base_delay_seconds, max=60
            ),
            retry=retry_if_exception_type((RateLimitError, ProviderResponseError)),
        )

    # -- generation --------------------------------------------------------- #
    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        client = self._get_client()

        @self._retryer()
        def _call() -> dict[str, Any]:
            from google.genai import types

            config_kwargs: dict[str, Any] = {
                "response_mime_type": "application/json",
                "temperature": (
                    request.temperature
                    if request.temperature is not None
                    else settings.gemini_temperature
                ),
                "max_output_tokens": request.max_tokens,
            }
            if request.system:
                config_kwargs["system_instruction"] = request.system
            if request.response_schema:
                config_kwargs["response_schema"] = request.response_schema

            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=request.prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
            except Exception as exc:  # noqa: BLE001 - SDK raises varied types
                if _is_rate_limit(exc):
                    raise RateLimitError(str(exc)) from exc
                raise ProviderResponseError(f"Gemini generation failed: {exc}") from exc

            text = getattr(response, "text", None)
            if not text:
                raise ProviderResponseError("Gemini returned an empty response")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProviderResponseError(
                    f"Gemini returned non-JSON output: {exc}"
                ) from exc
            if not isinstance(data, dict):
                raise ProviderResponseError("Gemini JSON root was not an object")
            return data

        return _call()

    # -- embeddings --------------------------------------------------------- #
    def embed(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()

        @self._retryer()
        def _call() -> list[list[float]]:
            from google.genai import types

            try:
                response = client.models.embed_content(
                    model=self.embedding_model,
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.embedding_dim,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                if _is_rate_limit(exc):
                    raise RateLimitError(str(exc)) from exc
                raise ProviderResponseError(f"Gemini embedding failed: {exc}") from exc

            embeddings = getattr(response, "embeddings", None)
            if not embeddings:
                raise ProviderResponseError("Gemini returned no embeddings")
            return [_l2_normalize(list(e.values)) for e in embeddings]

        return _call()


class GeminiImageProvider(ImageProvider):
    """Image generation stays out of scope until the Visual Director (Phase 3)."""

    name = "gemini-imagen"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_image_model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.is_available():
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        raise NotImplementedError(
            "Image generation is wired in Phase 3 (Visual Director)."
        )
