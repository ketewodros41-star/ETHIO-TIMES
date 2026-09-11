"""Unit tests for URL/content normalization helpers."""

from __future__ import annotations

from app.pipelines.normalize import canonicalize_url, content_hash, strip_html


def test_canonicalize_strips_tracking_and_fragment():
    url = "HTTPS://Example.com/Story/?utm_source=twitter&id=5#section"
    assert canonicalize_url(url) == "https://example.com/Story?id=5"


def test_canonicalize_resolves_relative_against_base():
    assert (
        canonicalize_url("/news/item-1", base_url="https://addisstandard.com")
        == "https://addisstandard.com/news/item-1"
    )


def test_canonicalize_removes_trailing_slash():
    assert canonicalize_url("https://example.com/a/b/") == "https://example.com/a/b"


def test_strip_html_collapses_whitespace():
    assert strip_html("<p>Hello   <b>world</b></p>\n") == "Hello world"


def test_content_hash_is_stable_and_order_sensitive():
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("b", "a")
