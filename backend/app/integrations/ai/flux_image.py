"""Photorealistic image provider for ETHIOTIMES.

Supports:
1. Together AI (FLUX.1-schnell, cost-effective paid API when TOGETHER_API_KEY is configured).
2. OpenRouter (when OPENROUTER_API_KEY is configured).
3. Free FLUX generator via Pollinations (editorial 1080x1350 photorealism, $0.00, no key required).
4. Google Imagen (only if explicitly enabled with Gemini Enterprise credentials).
"""
from __future__ import annotations

import base64
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
    _gemini_disabled: bool = False

    def is_available(self) -> bool:
        return True

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        w = request.width or 1080
        h = request.height or 1350
        prompt_clean = request.prompt.replace("\n", " ").strip()

        # 1. Together AI FLUX (Cost-effective fast API: ~$0.003/image)
        if getattr(settings, "together_api_key", None):
            try:
                result = self._generate_together(prompt_clean, w, h)
                if result:
                    return result
            except Exception as exc:
                logger.warning("together_image_failed_fallback", error=str(exc))

        # 2. OpenRouter Image API (if configured)
        if getattr(settings, "openrouter_api_key", None):
            try:
                result = self._generate_openrouter(prompt_clean, w, h)
                if result:
                    return result
            except Exception as exc:
                logger.warning("openrouter_image_failed_fallback", error=str(exc))

        # 3. Gemini Imagen (Only if user explicitly chose 'gemini' and it hasn't failed before)
        if (
            getattr(settings, "image_provider_preference", "flux") == "gemini"
            and settings.gemini_api_key
            and not EditorialImageProvider._gemini_disabled
        ):
            try:
                from google import genai
                client = genai.Client(api_key=settings.gemini_api_key)
                aspect = "4:5" if h > w else "1:1"
                res = client.models.generate_images(
                    model=getattr(settings, "gemini_image_model", "imagen-3.0-generate-002"),
                    prompt=prompt_clean,
                    config=dict(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio=aspect,
                    ),
                )
                if res.generated_images and res.generated_images[0].image.image_bytes:
                    logger.info("gemini_imagen_success", prompt=prompt_clean[:60])
                    return ImageGenerationResult(
                        image_url=None,
                        image_bytes=res.generated_images[0].image.image_bytes,
                        model="gemini-imagen-3",
                        raw={"provider": "gemini"},
                    )
            except Exception as exc:
                EditorialImageProvider._gemini_disabled = True
                logger.warning("gemini_imagen_failed_fallback", error=str(exc))

        # 4. Free FLUX Generator (Black Forest Labs FLUX.1 via Pollinations, $0.00, 1080x1350)
        try:
            encoded_prompt = urllib.parse.quote(prompt_clean[:400])
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

        # 5. Fallback placeholder
        logger.info("mock_image_fallback")
        return ImageGenerationResult(
            image_url=None,
            image_bytes=_PLACEHOLDER_PNG,
            model="placeholder-fallback",
            raw={"fallback": True},
        )

    def _generate_together(self, prompt: str, width: int, height: int) -> ImageGenerationResult | None:
        """Call Together AI's FLUX.1-schnell endpoint."""
        url = "https://api.together.xyz/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.together_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "black-forest-labs/FLUX.1-schnell",
            "prompt": prompt,
            "width": width if width <= 1024 else 1024,
            "height": height if height <= 1024 else 1024,
            "steps": 4,
            "n": 1,
            "response_format": "b64_json",
        }
        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                b64 = data["data"][0]["b64_json"]
                img_bytes = base64.b64decode(b64)
                logger.info("together_flux_success", bytes_len=len(img_bytes))
                return ImageGenerationResult(
                    image_url=None,
                    image_bytes=img_bytes,
                    model="together-flux-schnell",
                    raw={"provider": "together"},
                )
        return None

    def _generate_openrouter(self, prompt: str, width: int, height: int) -> ImageGenerationResult | None:
        """Call OpenRouter images endpoint if available."""
        url = "https://openrouter.ai/api/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "black-forest-labs/flux-1-schnell",
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
        }
        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                img_url = data["data"][0].get("url")
                if img_url:
                    dl = client.get(img_url)
                    if dl.status_code == 200:
                        return ImageGenerationResult(
                            image_url=None,
                            image_bytes=dl.content,
                            model="openrouter-flux",
                            raw={"provider": "openrouter"},
                        )
        return None
