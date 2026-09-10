"""Photorealistic image provider for ETHIOTIMES.

Attempts Gemini Imagen first; automatically falls back to FLUX
high-resolution photorealistic generation (1080x1350 editorial ratio),
and ultimately to mock placeholder in offline/test environments.
"""
from __future__ import annotations

import urllib.parse
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProvider,
)
from app.integrations.ai.mock_image import _PLACEHOLDER_PNG

logger = get_logger(__name__)


class EditorialImageProvider(ImageProvider):
    name = "editorial-flux"

    def is_available(self) -> bool:
        return True

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        # 1. Try Gemini Imagen if configured
        if settings.gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=settings.gemini_api_key)
                aspect = "4:5" if request.height > request.width else "1:1"
                res = client.models.generate_images(
                    model=getattr(settings, "gemini_image_model", "imagen-3.0-generate-002"),
                    prompt=request.prompt,
                    config=dict(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio=aspect,
                    ),
                )
                if res.generated_images and res.generated_images[0].image.image_bytes:
                    logger.info("gemini_imagen_success", prompt=request.prompt[:60])
                    return ImageGenerationResult(
                        image_url=None,
                        image_bytes=res.generated_images[0].image.image_bytes,
                        model="gemini-imagen-3",
                        raw={"provider": "gemini"},
                    )
            except Exception as exc:
                logger.warning("gemini_imagen_failed_fallback", error=str(exc))

        # 2. Photorealistic FLUX generator (editorial 1080x1350)
        try:
            prompt_clean = request.prompt.replace("\n", " ").strip()
            encoded_prompt = urllib.parse.quote(prompt_clean[:400])
            w = request.width or 1080
            h = request.height or 1350
            flux_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={w}&height={h}&model=flux&nologo=true"

            with httpx.Client(timeout=45.0, follow_redirects=True) as http_client:
                res = http_client.get(flux_url)
                if res.status_code == 200 and len(res.content) > 1000:
                    logger.info("flux_image_success", bytes_len=len(res.content))
                    return ImageGenerationResult(
                        image_url=None,
                        image_bytes=res.content,
                        model="flux-editorial",
                        raw={"provider": "flux", "url": flux_url},
                    )
        except Exception as exc:
            logger.warning("flux_image_failed", error=str(exc))

        # 3. Fallback placeholder
        logger.info("mock_image_fallback")
        return ImageGenerationResult(
            image_url=None,
            image_bytes=_PLACEHOLDER_PNG,
            model="placeholder-fallback",
            raw={"fallback": True},
        )
