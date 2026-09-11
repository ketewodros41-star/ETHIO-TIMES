"""Provider-agnostic AI interfaces.

Phase 2 implements a real Gemini provider behind these interfaces. Providers
return **structured JSON** (a plain ``dict``) that services validate against the
Pydantic contracts in ``app.schemas.intelligence``. Providers also expose text
embeddings. Concrete providers live alongside this module (see ``gemini.py``).

Design rules:
- Providers never log or echo secrets.
- Providers are only invoked from Celery workers, never request handlers.
- Callers handle ``ProviderNotConfiguredError`` (no key) and ``RateLimitError``
  (quota) explicitly; other failures surface as ``ProviderResponseError``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextGenerationRequest:
    prompt: str
    system: str | None = None
    max_tokens: int = 2048
    temperature: float | None = None
    # JSON schema constraining the response (google-genai `response_schema`).
    response_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextGenerationResult:
    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationRequest:
    prompt: str
    width: int = 1080
    height: int = 1350
    style: str | None = None
    reference_images: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationResult:
    image_url: str | None
    image_bytes: bytes | None
    model: str
    raw: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ProviderError(RuntimeError):
    """Base class for provider errors."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is used without required configuration (e.g. key)."""


class RateLimitError(ProviderError):
    """Raised when the provider signals quota/rate-limit exhaustion (HTTP 429)."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds the configured timeout."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an unusable/unparseable response."""


# --------------------------------------------------------------------------- #
# Interfaces
# --------------------------------------------------------------------------- #
class AIProvider(ABC):
    """Abstraction over a text/LLM provider."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider has the configuration needed to run."""

    @abstractmethod
    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        """Return a parsed JSON object from a constrained generation call."""

    @abstractmethod
    def embed(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Return one embedding vector per input text (L2-normalized)."""


class ImageProvider(ABC):
    """Abstraction over an image-generation provider."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
