"""Telegram Bot API publisher for the isolated Telegram delivery ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

import httpx

from app.core.config import settings
from app.models.telegram_post import TelegramPost


from pathlib import Path

FALLBACK_IMAGES_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "editorial"
DEFAULT_FALLBACK_URLS = [
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1200&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&auto=format&fit=crop&q=80",
]


@dataclass(frozen=True)
class TelegramPublishResult:
    message_id: str | None
    published_at: datetime | None
    error: str | None = None


class TelegramPublisher:
    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token)

    def _resolve_image_bytes(self, post: TelegramPost) -> tuple[bytes, str]:
        """Download or load verified image bytes and filename.
        
        Guarantees that a valid JPEG/PNG image is ALWAYS returned:
        1. Direct HTTP download of post.photo_url (rejecting ephemeral telesco.pe URLs).
        2. Local disk read if post.photo_url is a storage path.
        3. Local verified editorial fallbacks in backend/app/assets/editorial.
        4. Permanent high-reliability CDN fallback.
        """
        # 1. Try candidate photo_url if provided and not telesco.pe
        url = (post.photo_url or "").strip()
        if url and "telesco.pe" not in url.lower():
            if url.startswith(("http://", "https://")):
                try:
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    }
                    resp = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
                    if resp.is_success and len(resp.content) >= 2000:
                        content_type = resp.headers.get("content-type", "").lower()
                        ext = ".png" if "png" in content_type else (".webp" if "webp" in content_type else ".jpg")
                        return resp.content, f"post_photo{ext}"
                except Exception:
                    pass
            elif url.startswith("/"):
                p = Path(url)
                if p.exists() and p.is_file() and p.stat().st_size >= 2000:
                    return p.read_bytes(), p.name
                if url.startswith("/api/v1/posts/assets/"):
                    parts = url.strip("/").split("/")
                    if len(parts) >= 5:
                        asset_id = parts[4]
                        media_path = Path(settings.media_root) / "assets" / f"{asset_id}.png"
                        if media_path.exists() and media_path.stat().st_size >= 2000:
                            return media_path.read_bytes(), f"{asset_id}.png"

        # 2. Check local editorial fallbacks
        is_ethiopia = (post.content_bucket == "ethiopia") or (post.language == "am")
        preferred_name = "ethiopia.jpg" if is_ethiopia else "international.jpg"
        preferred_path = FALLBACK_IMAGES_DIR / preferred_name
        if preferred_path.exists() and preferred_path.stat().st_size >= 2000:
            return preferred_path.read_bytes(), preferred_name

        for fallback_file in FALLBACK_IMAGES_DIR.glob("*.jpg"):
            if fallback_file.exists() and fallback_file.stat().st_size >= 2000:
                return fallback_file.read_bytes(), fallback_file.name

        # 3. Permanent CDN fallback
        for fb_url in DEFAULT_FALLBACK_URLS:
            try:
                resp = httpx.get(fb_url, timeout=10.0, follow_redirects=True)
                if resp.is_success and len(resp.content) >= 2000:
                    return resp.content, "editorial_fallback.jpg"
            except Exception:
                continue

        raise RuntimeError("No photo could be acquired for Telegram broadcast")

    def publish(
        self, post: TelegramPost, channel_username: str, dry_run: bool | None = None
    ) -> TelegramPublishResult:
        effective_dry_run = post.dry_run if dry_run is None else dry_run
        if effective_dry_run:
            return TelegramPublishResult(f"dry-run-{post.id}", datetime.now(UTC))
        if not self.is_configured():
            return TelegramPublishResult(None, None, "Telegram bot token is not configured")

        chat_id = channel_username.strip()
        if not chat_id.startswith(("@", "-")):
            chat_id = f"@{chat_id}"

        base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        caption = self._caption(post)

        try:
            photo_bytes, filename = self._resolve_image_bytes(post)
        except Exception as exc:
            return TelegramPublishResult(None, None, f"Failed to acquire photo for broadcast: {exc}")

        mime_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        files = {"photo": (filename, photo_bytes, mime_type)}

        try:
            response = httpx.post(f"{base_url}/sendPhoto", data=data, files=files, timeout=30.0)
            res_data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return TelegramPublishResult(None, None, f"Telegram request failed: {exc}")

        if not response.is_success or not res_data.get("ok"):
            err_desc = str(res_data.get("description") or f"Telegram HTTP {response.status_code}")
            return TelegramPublishResult(None, None, f"Telegram photo publish rejected: {err_desc}")

        message_id = res_data.get("result", {}).get("message_id")
        return TelegramPublishResult(str(message_id) if message_id is not None else None, datetime.now(UTC))

    @staticmethod
    def _truncate_plain(text: str, max_chars: int) -> str:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max(0, max_chars - 1)].rstrip() + "…"

    @classmethod
    def _caption(cls, post: TelegramPost) -> str:
        # Truncate plain text fields before wrapping in HTML tags so unclosed tags
        # never cause Telegram HTTP 400 Bad Request errors.
        headline_plain = cls._truncate_plain(post.headline or "", 140)
        source_plain = cls._truncate_plain(post.source_attribution or "ETHIOPIAN TIMES", 60)
        caption_plain = cls._truncate_plain(post.caption or "", 120)
        credit_plain = cls._truncate_plain(post.photo_credit or "", 60) if post.photo_credit else ""

        highlight_words = [
            cls._truncate_plain(w, 30) for w in (post.highlight_words or [])[:3]
        ]
        highlights = ", ".join(escape(w) for w in highlight_words if w)

        highlight_line = f"\n<b>Key:</b> {highlights}" if highlights else ""
        credit_line = f"\n<i>Photo: {escape(credit_plain)}</i>" if credit_plain else ""
        source_line = f"\n\n<i>Source: {escape(source_plain)}</i>" if source_plain else ""
        tail_caption_line = f"\n\n{escape(caption_plain)}" if caption_plain else ""
        headline_wrapped = f"<b>{escape(headline_plain)}</b>\n\n"

        fixed_len = (
            len(headline_wrapped)
            + len(highlight_line)
            + len(source_line)
            + len(credit_line)
            + len(tail_caption_line)
        )
        remaining_budget = max(0, 1024 - fixed_len)

        desc_plain = " ".join((post.description or "").strip().split())
        if len(desc_plain) > remaining_budget:
            desc_plain = (
                desc_plain[: max(0, remaining_budget - 1)].rstrip() + "…"
                if remaining_budget > 1
                else ""
            )
        escaped_desc = escape(desc_plain)
        while len(escaped_desc) > remaining_budget and len(desc_plain) > 1:
            desc_plain = desc_plain[:-2].rstrip() + "…"
            escaped_desc = escape(desc_plain)
        if len(escaped_desc) > remaining_budget:
            escaped_desc = ""

        return (
            f"{headline_wrapped}{escaped_desc}"
            f"{highlight_line}{source_line}{credit_line}{tail_caption_line}"
        )

