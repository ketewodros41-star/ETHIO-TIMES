"""Normalization helpers used during ingestion."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse, urlunparse

# Tracking params we strip to improve deduplication by canonical URL.
_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_cid|mc_eid|ref|source)", re.I)
_WHITESPACE = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")


def canonicalize_url(url: str, base_url: str | None = None) -> str:
    """Return a stable canonical form of a URL for deduplication.

    Resolves against `base_url` if relative, lowercases the scheme/host, drops
    fragments and common tracking query parameters, and removes a trailing slash.
    """
    if base_url:
        url = urljoin(base_url, url)
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()

    query_parts = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            key = pair.split("=", 1)[0]
            if not _TRACKING_PARAMS.match(key):
                query_parts.append(pair)
    query = "&".join(query_parts)

    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", query, ""))


def strip_html(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = _HTML_TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", cleaned).strip()


def content_hash(*parts: str | None) -> str:
    """Stable hash of content parts, used to detect edits/versions."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update((part or "").encode("utf-8", errors="ignore"))
        hasher.update(b"\x00")
    return hasher.hexdigest()
