"""Telegram channel adapter.

Ingests from verified public channels via the public web preview (`https://t.me/s/{username}`).
Extracts text messages, dates, permalinks, and embedded high-res photos.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger
from app.pipelines.adapters.base import AdapterError, BaseSourceAdapter, FetchedItem

logger = get_logger(__name__)


class TelegramSourceAdapter(BaseSourceAdapter):
    source_type_label = "telegram"

    def can_handle(self) -> bool:
        username = self._get_username()
        return bool(username)

    def _get_username(self) -> str | None:
        if self.source.telegram_username:
            return self.source.telegram_username.lstrip("@").strip()
        if self.source.telegram_url:
            match = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_+]+)", self.source.telegram_url)
            if match:
                return match.group(1)
        if self.source.website and "t.me" in self.source.website:
            match = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_+]+)", self.source.website)
            if match:
                return match.group(1)
        return None

    def fetch(self) -> list[FetchedItem]:
        username = self._get_username()
        if not username:
            raise AdapterError(f"Source {self.source.id} has no telegram_username or telegram_url")

        url = f"https://t.me/s/{username}"
        headers = {
            "User-Agent": getattr(settings, "ingest_user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            with httpx.Client(timeout=float(getattr(settings, "ingest_http_timeout_seconds", 20)), follow_redirects=True) as client:
                res = client.get(url, headers=headers)
                if res.status_code != 200:
                    raise AdapterError(f"HTTP {res.status_code} fetching Telegram channel {url}")
                html = res.text
        except Exception as exc:
            raise AdapterError(f"Failed to fetch Telegram channel {url}: {exc}") from exc

        soup = BeautifulSoup(html, "html.parser")
        message_divs = soup.find_all("div", class_="tgme_widget_message")
        if not message_divs:
            logger.info("telegram_no_messages_found", channel=username)
            return []

        items: list[FetchedItem] = []
        for m in message_divs:
            text_el = m.find("div", class_="tgme_widget_message_text")
            photo_el = m.find("a", class_="tgme_widget_message_photo_wrap")
            time_el = m.find("time")
            link_el = m.find("a", class_="tgme_widget_message_date")

            text = text_el.get_text(separator=" ", strip=True) if text_el else ""
            if not text and not photo_el:
                continue

            # Extract permalink
            canonical_url = link_el["href"] if link_el and "href" in link_el.attrs else f"https://t.me/{username}/{m.get('data-post', '')}"

            # Extract photo URL from style background-image
            photo_url = None
            if photo_el and "style" in photo_el.attrs:
                style = photo_el["style"]
                match = re.search(r"background-image:url\('([^']+)'\)", style)
                if match:
                    photo_url = match.group(1)

            # Extract publication timestamp
            published_at = None
            if time_el and "datetime" in time_el.attrs:
                try:
                    published_at = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                except ValueError:
                    published_at = datetime.now(UTC)

            # Derive headline title from first sentence/line or first 120 chars
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            first_line = lines[0] if lines else "Tikvah Ethiopia Update"
            title = first_line[:150]
            if len(first_line) > 150:
                title = title[:147] + "..."

            items.append(
                FetchedItem(
                    canonical_url=canonical_url,
                    url=canonical_url,
                    title=title,
                    summary=text[:1000] if text else title,
                    content=text,
                    author=self.source.name or "Tikvah Ethiopia",
                    language=self.source.language or "am",
                    categories=["telegram", "breaking"],
                    image_url=photo_url,
                    published_at=published_at,
                    raw_payload={"channel": username, "has_photo": bool(photo_url)},
                )
            )

        logger.info("telegram_ingest_success", channel=username, count=len(items))
        return items

