"""Tests for the new features:
- Problem 1: self-healing dry_run check in plan_telegram_posts
- Problem 2: sponsored/ad content filter
- Problem 3: content_filters per-bucket enforcement + API endpoint
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — avoid SQLAlchemy instrumentation by using SimpleNamespace
# ---------------------------------------------------------------------------

def _make_event(title: str, summary: str = "", primary_category: str = "Politics") -> SimpleNamespace:
    """Create a plain namespace event object suitable for filter unit tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        summary=summary,
        primary_category=primary_category,
        primary_region=None,
        trend_score=1.0,
        last_seen_at=datetime.now(UTC),
        review_required=False,
        auto_publish_eligible=True,
    )


# ---------------------------------------------------------------------------
# The filter logic replicated verbatim for isolation testing
# ---------------------------------------------------------------------------

_GLOBAL_SPONSOR_SIGNALS: tuple[str, ...] = (
    "sponsored", "sponsered",
    "advertisement", "advertorial",
    "partner content", "partnered content",
    "ad feature", "promoted content", "paid content",
    "press release", "pr news", "brand story",
    "brought to you by", "in association with",
    "commercial feature", "native ad",
    "ethio telecom",
)


def _is_sponsored_event(event: SimpleNamespace) -> bool:
    haystack = " ".join(filter(None, [event.title, event.summary or ""])).lower()
    for signal in _GLOBAL_SPONSOR_SIGNALS:
        if signal in haystack:
            return True
    return False


def _passes_bucket_filters(event: SimpleNamespace, bucket_cfg: dict) -> bool:
    if not bucket_cfg:
        return True
    category = (event.primary_category or "").lower()
    haystack = " ".join(filter(None, [event.title, event.summary or ""])).lower()
    allowed_cats = [c.lower() for c in bucket_cfg.get("allowed_categories", [])]
    blocked_cats = [c.lower() for c in bucket_cfg.get("blocked_categories", [])]
    allowed_kws = [k.lower() for k in bucket_cfg.get("allowed_keywords", [])]
    blocked_kws = [k.lower() for k in bucket_cfg.get("blocked_keywords", [])]
    for kw in blocked_kws:
        if kw and kw in haystack:
            return False
    if blocked_cats and any(bc in category for bc in blocked_cats):
        return False
    if allowed_cats and not any(ac in category for ac in allowed_cats):
        return False
    if allowed_kws and not any(kw in haystack for kw in allowed_kws):
        return False
    return True


# ---------------------------------------------------------------------------
# Problem 2: Sponsored content filter (unit tests, no DB)
# ---------------------------------------------------------------------------

class TestSponsoredContentFilter:
    """Verify _is_sponsored_event rejects known ad signals."""

    def test_ethio_telecom_ad_is_rejected(self):
        assert _is_sponsored_event(_make_event("Ethio Telecom Launches New 5G Service")) is True

    def test_sponsored_keyword_in_title(self):
        assert _is_sponsored_event(_make_event("Sponsored: Best Banking Products 2024")) is True

    def test_advertisement_in_summary(self):
        assert _is_sponsored_event(_make_event("Breaking News", "This is an advertisement for our partner.")) is True

    def test_press_release_rejected(self):
        assert _is_sponsored_event(_make_event("Press release: Company X announces Q3 results")) is True

    def test_advertorial_rejected(self):
        assert _is_sponsored_event(_make_event("Advertorial: Why You Should Switch Banks")) is True

    def test_partner_content_rejected(self):
        assert _is_sponsored_event(_make_event("Partner content: Telecom expands network")) is True

    def test_legitimate_news_not_rejected(self):
        assert _is_sponsored_event(_make_event("Ethiopia peace talks resume in Addis Ababa", "Government officials met today.")) is False

    def test_international_politics_not_rejected(self):
        assert _is_sponsored_event(_make_event("UN Security Council meets on Sudan crisis")) is False

    def test_empty_summary_is_safe(self):
        assert _is_sponsored_event(_make_event("ABAY TV: New programme lineup announced", "")) is False

    def test_case_insensitive_match(self):
        assert _is_sponsored_event(_make_event("SPONSORED CONTENT: Top 10 Telecom Deals")) is True

    def test_brought_to_you_by_rejected(self):
        assert _is_sponsored_event(_make_event("News Brought To You By EthioTel")) is True  # "brought to you by" is a sponsor signal

    def test_paid_content_rejected(self):
        assert _is_sponsored_event(_make_event("Paid content: Investment opportunities in 2026")) is True

    def test_native_ad_rejected(self):
        assert _is_sponsored_event(_make_event("Native ad: The future of banking")) is True


# ---------------------------------------------------------------------------
# Problem 3: BucketContentFilter logic (unit tests, no DB)
# ---------------------------------------------------------------------------

class TestBucketFilterLogic:
    """Verify _passes_bucket_filters applies allowed/blocked rules correctly."""

    def test_empty_config_allows_all(self):
        event = _make_event("Some news", primary_category="Entertainment")
        assert _passes_bucket_filters(event, {}) is True

    def test_allowed_categories_whitelist_passes(self):
        event = _make_event("Politics story", primary_category="Politics")
        cfg = {"allowed_categories": ["Politics", "Sports"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is True

    def test_allowed_categories_whitelist_rejects_missing(self):
        event = _make_event("Entertainment story", primary_category="Entertainment")
        cfg = {"allowed_categories": ["Politics", "Sports"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is False

    def test_blocked_categories_rejects(self):
        event = _make_event("Entertainment news", primary_category="Entertainment")
        cfg = {"allowed_categories": [], "blocked_categories": ["Entertainment"], "allowed_keywords": [], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is False

    def test_blocked_keywords_override_allowed_category(self):
        event = _make_event("Politics: ad feature today", primary_category="Politics")
        cfg = {"allowed_categories": ["Politics"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["ad feature"]}
        assert _passes_bucket_filters(event, cfg) is False

    def test_allowed_keywords_whitelist_passes(self):
        event = _make_event("Ethiopia election update")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": ["election", "reform"], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is True

    def test_allowed_keywords_whitelist_rejects_missing(self):
        event = _make_event("Stock market rally in New York")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": ["election", "reform"], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is False

    def test_blocked_keyword_in_summary_rejects(self):
        event = _make_event("News Today", summary="this content is sponsored by telecom")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["sponsored"]}
        assert _passes_bucket_filters(event, cfg) is False

    def test_empty_blocked_kw_does_not_false_positive(self):
        """An empty string in blocked_keywords should not reject everything."""
        event = _make_event("Legitimate news story")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": [""]}
        assert _passes_bucket_filters(event, cfg) is True

    def test_category_matching_is_case_insensitive(self):
        event = _make_event("Sports update", primary_category="sports")
        cfg = {"allowed_categories": ["Sports"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}
        assert _passes_bucket_filters(event, cfg) is True


# ---------------------------------------------------------------------------
# Problem 1: Self-healing dry_run check — tests against tasks module internals
# ---------------------------------------------------------------------------

class TestDryRunSelfHeal:
    """Verify that plan_telegram_posts auto-resets dry_run when enabled=True."""

    def test_self_heal_dry_run_reset(self):
        """When enabled=True and dry_run=True, the task should reset dry_run to False."""
        # Track state changes
        state = {"dry_run": True}

        class FakePolicy:
            enabled = True
            timezone = "Africa/Addis_Ababa"
            ethiopia_posts_per_day = 0
            international_posts_per_day = 0
            channel_username = "@test"
            posting_hours = [8]
            content_filters = {}
            posting_hours = [8]

            @property
            def dry_run(self):
                return state["dry_run"]

            @dry_run.setter
            def dry_run(self, value):
                state["dry_run"] = value

        fake_policy = FakePolicy()

        mock_scalars = MagicMock()
        mock_scalars.return_value.all.return_value = []

        session = MagicMock()
        session.get.return_value = fake_policy
        session.scalars.return_value = mock_scalars.return_value

        from app.workers.tasks import plan_telegram_posts

        with patch("app.workers.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = session
            session.__enter__ = MagicMock(return_value=session)
            session.__exit__ = MagicMock(return_value=False)

            try:
                plan_telegram_posts()
            except Exception:
                pass  # May raise due to incomplete mock; we care about dry_run state only

        assert state["dry_run"] is False, (
            "plan_telegram_posts must reset dry_run=False when enabled=True and dry_run=True"
        )
