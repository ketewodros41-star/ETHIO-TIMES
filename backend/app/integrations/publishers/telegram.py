"""Telegram Bot API publisher for the isolated Telegram delivery ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

import httpx

from app.core.config import settings
from app.models.telegram_post import TelegramPost


@dataclass(frozen=True)
class TelegramPublishResult:
    message_id: str | None
    published_at: datetime | None
    error: str | None = None


class TelegramPublisher:
    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token)

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
        payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        endpoint = "sendPhoto" if post.photo_url else "sendMessage"
        if post.photo_url:
            payload["photo"] = post.photo_url
        else:
            payload["text"] = caption
            payload.pop("caption")

        try:
            response = httpx.post(f"{base_url}/{endpoint}", data=payload, timeout=20.0)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return TelegramPublishResult(None, None, f"Telegram request failed: {exc}")
        if not response.is_success or not data.get("ok"):
            if endpoint == "sendPhoto":
                try:
                    fallback_payload = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
                    fb_resp = httpx.post(f"{base_url}/sendMessage", data=fallback_payload, timeout=20.0)
                    fb_data = fb_resp.json()
                    if fb_resp.is_success and fb_data.get("ok"):
                        msg_id = fb_data.get("result", {}).get("message_id")
                        return TelegramPublishResult(str(msg_id) if msg_id is not None else None, datetime.now(UTC))
                except Exception:
                    pass
            return TelegramPublishResult(None, None, str(data.get("description") or "Telegram rejected the post"))
        message_id = data.get("result", {}).get("message_id")
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

