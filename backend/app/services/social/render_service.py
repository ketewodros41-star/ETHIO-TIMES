"""Playwright render service (Phase 5)."""
from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.models.social_post import SocialPost

FORMAT_DIMENSIONS = {
    "portrait": (1080, 1350),
    "square":   (1080, 1080),
    "story":    (1080, 1920),
}

_PLACEHOLDER_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

logger = get_logger(__name__)

class RenderError(RuntimeError):
    pass

class RenderService:
    def render_post(self, post: SocialPost) -> Path:
        media_dir = Path(settings.media_root) / "renders"
        media_dir.mkdir(parents=True, exist_ok=True)
        out_path = media_dir / f"{post.id}.png"

        if settings.mock_render:
            logger.info("render_mock", post_id=str(post.id))
            out_path.write_bytes(_PLACEHOLDER_PNG)
            return out_path

        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError as exc:
            raise RenderError("playwright not installed") from exc

        fmt = post.format.value if hasattr(post.format, "value") else post.format
        width, height = FORMAT_DIMENSIONS.get(fmt, (1080, 1350))
        url = f"{settings.next_public_url}/render/{post.id}?format={fmt}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, timeout=settings.playwright_timeout_ms)
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": width, "height": height})
            browser.close()

        logger.info("render_complete", post_id=str(post.id), path=str(out_path))
        return out_path

    def render_carousel_slides(self, post: SocialPost) -> list[Path]:
        """Render each slide of a carousel post."""
        slides = (post.eligibility_snapshot or {}).get("carousel_slides", [])
        if not slides:
            return [self.render_post(post)]

        media_dir = Path(settings.media_root) / "renders" / str(post.id)
        media_dir.mkdir(parents=True, exist_ok=True)
        rendered_paths = []

        if settings.mock_render:
            for i in range(len(slides)):
                slide_path = media_dir / f"slide_{i + 1}.png"
                slide_path.write_bytes(_PLACEHOLDER_PNG)
                rendered_paths.append(slide_path)
            return rendered_paths

        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError as exc:
            raise RenderError("playwright not installed") from exc

        fmt = post.format.value if hasattr(post.format, "value") else post.format
        width, height = FORMAT_DIMENSIONS.get(fmt, (1080, 1350))

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            for i in range(len(slides)):
                slide_path = media_dir / f"slide_{i + 1}.png"
                url = f"{settings.next_public_url}/render/{post.id}?format={fmt}&slide={i + 1}"
                page.goto(url, timeout=settings.playwright_timeout_ms)
                page.screenshot(path=str(slide_path), clip={"x": 0, "y": 0, "width": width, "height": height})
                rendered_paths.append(slide_path)
            browser.close()

        logger.info("carousel_render_complete", post_id=str(post.id), slides=len(rendered_paths))
        return rendered_paths
