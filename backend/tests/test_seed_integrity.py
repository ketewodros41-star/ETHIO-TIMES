"""Guards on the seed source registry."""

from __future__ import annotations

from app.data.sources_seed import SEED_SOURCES
from app.models.enums import SourceType


def test_seed_has_10_to_20_sources():
    assert 10 <= len(SEED_SOURCES) <= 20


def test_seed_slugs_are_unique():
    slugs = [s["slug"] for s in SEED_SOURCES]
    assert len(slugs) == len(set(slugs))


def test_seed_source_types_are_valid():
    valid = {t.value for t in SourceType}
    for src in SEED_SOURCES:
        assert src["source_type"] in valid


def test_telegram_sources_are_not_fabricated_and_flagged():
    for src in SEED_SOURCES:
        if src["source_type"] == SourceType.telegram_channel.value:
            # No invented @handle, and must require verification.
            assert not src.get("telegram_username")
            assert src.get("verification_status") == "needs_verification"


def test_at_least_some_real_rss_feeds_present():
    with_rss = [s for s in SEED_SOURCES if s.get("rss_url")]
    assert len(with_rss) >= 5
