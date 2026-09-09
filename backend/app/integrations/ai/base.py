"""Provider-agnostic AI interfaces.

Phase 1 defines the abstractions only. The full analysis, summarization,
relevance-classification, and image-generation pipelines are Phase 2+; concrete
providers here are stubs that document the contract and raise `NotImplemented`
style errors if invoked, so nothing accidentally calls a paid API in Phase 1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextGenerationRequest:
    prompt: str
    system: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.4
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


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a provider is used without required configuration."""


class AIProvider(ABC):
    """Abstraction over a text/LLM provider."""

    name: str = "base"

    @abstractmethod
    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResult:
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return an embedding vector per input text."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class ImageProvider(ABC):
    """Abstraction over an image-generation provider."""

    name: str = "base"

    @abstractmethod
    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
