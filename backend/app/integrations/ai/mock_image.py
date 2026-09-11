"""Mock image provider for tests and CI (no network calls)."""
from __future__ import annotations

from app.integrations.ai.base import ImageGenerationRequest, ImageGenerationResult, ImageProvider

_PLACEHOLDER_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

class MockImageProvider(ImageProvider):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return ImageGenerationResult(
            image_url=None,
            image_bytes=_PLACEHOLDER_PNG,
            model="mock-image-v1",
            raw={"mock": True, "prompt": request.prompt[:100]},
        )
