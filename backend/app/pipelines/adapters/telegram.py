"""Telegram channel adapter — Phase 1.5 stub.

Ethiopian breaking news frequently originates on Telegram (e.g. Tikvah
Ethiopia). Phase 1.5 will ingest from verified public channels via the Telegram
API / MTProto or a bot, after handles are confirmed from official sources.

IMPORTANT: Telegram is rife with impersonation. Never ingest from a channel
whose @handle has not been verified against the outlet's official website.
Sources of type `telegram_channel` are seeded with
`verification_status = needs_verification` and remain inactive until confirmed.
"""

from __future__ import annotations

from app.pipelines.adapters.base import BaseSourceAdapter, FetchedItem


class TelegramSourceAdapter(BaseSourceAdapter):
    source_type_label = "telegram"

    def can_handle(self) -> bool:
        return bool(self.source.telegram_username or self.source.telegram_url)

    def fetch(self) -> list[FetchedItem]:
        raise NotImplementedError(
            "TelegramSourceAdapter is implemented in Phase 1.5 for verified channels."
        )
