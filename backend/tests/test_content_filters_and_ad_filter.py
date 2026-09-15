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
# Direct import of filter logic from tasks module
# ---------------------------------------------------------------------------

from app.workers.tasks import (
    _GLOBAL_SPONSOR_SIGNALS,
    _is_sponsored_event,
    _passes_bucket_filters,
    normalize_filter_text,
    plan_telegram_posts,
)


# ---------------------------------------------------------------------------
# Problem 2: Sponsored content filter (unit tests, English & Amharic)
# ---------------------------------------------------------------------------

class TestSponsoredContentFilter:
    """Verify _is_sponsored_event rejects known ad signals across English and Amharic."""

    # --- English ad signals ---
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
        assert _is_sponsored_event(_make_event("News Brought To You By EthioTel")) is True

    def test_paid_content_rejected(self):
        assert _is_sponsored_event(_make_event("Paid content: Investment opportunities in 2026")) is True

    def test_native_ad_rejected(self):
        assert _is_sponsored_event(_make_event("Native ad: The future of banking")) is True

    # --- Amharic advertorials & brand PR signals ---
    def test_amharic_mastaweqiya_in_title(self):
        assert _is_sponsored_event(_make_event("ማስታወቂያ፡ አዲስ ስማርት ስልክ ለገበያ ቀረበ")) is True

    def test_amharic_mastaweqiya_in_summary(self):
        assert _is_sponsored_event(_make_event("አዲስ መኪና ደረሰ", "ይህ ለደንበኞቻችን የቀረበ ልዩ ማስታወቂያ ነው።")) is True

    def test_amharic_mastewawqiya_promotion(self):
        assert _is_sponsored_event(_make_event("ማስተዋወቂያ፡ ልዩ የበዓል ስጦታ እና ሽልማት")) is True

    def test_amharic_ethio_telecom_special_discount(self):
        assert _is_sponsored_event(_make_event("ኢትዮ ቴሌኮም ልዩ ቅናሽ ለአዲሱ ዓመት ይፋ አደረገ")) is True

    def test_amharic_ethio_telecom_punctuation_wordspace(self):
        # Ethiopic word divider ፡ used as separator
        assert _is_sponsored_event(_make_event("ኢትዮ፡ቴሌኮም አዲስ የኢንተርኔት ፓኬጅ አቀረበ")) is True

    def test_amharic_ethio_telecom_no_space(self):
        assert _is_sponsored_event(_make_event("የኢትዮቴሌኮም አዲስ አገልግሎት")) is True

    def test_amharic_telebirr_rejected(self):
        assert _is_sponsored_event(_make_event("ቴሌብር በመጠቀም የክፍያ ቅናሽ ያግኙ")) is True

    def test_amharic_telebirr_with_space(self):
        assert _is_sponsored_event(_make_event("ቴሌ ብር የሽልማት ፕሮግራም ተጀመረ")) is True

    def test_amharic_sponsor_yetederege(self):
        assert _is_sponsored_event(_make_event("ስፖንሰር የተደረገ፡ የቢዝነስ ምክሮች")) is True

    def test_amharic_sponsor_yetederege_with_ethiopic_full_stop(self):
        # Ethiopic full stop ።
        assert _is_sponsored_event(_make_event("የባንክ አገልግሎቶች። ስፖንሰር የተደረገ።")) is True

    def test_amharic_ye_sponsor(self):
        assert _is_sponsored_event(_make_event("የስፖንሰር ይዘት፡ ምርጥ የኢንቨስትመንት አማራጮች")) is True

    def test_amharic_paid_content_yetekefelebet(self):
        assert _is_sponsored_event(_make_event("የተከፈለበት ይዘት፡ የቤት ሽያጭ ማስታወቂያ")) is True
        assert _is_sponsored_event(_make_event("የተከፈለበት የማስተዋወቅ መርሃግብር")) is True

    def test_amharic_commercial_ad_yengid_mastaweqiya(self):
        assert _is_sponsored_event(_make_event("የንግድ ማስታወቂያ፡ ታላቅ የዋጋ ቅናሽ")) is True

    def test_amharic_press_release_gazetawi_meglecha(self):
        assert _is_sponsored_event(_make_event("ጋዜጣዊ መግለጫ፡ የኩባንያው ዓመታዊ ሪፖርት")) is True

    def test_amharic_press_release_with_ethiopic_comma(self):
        # Ethiopic comma ፣
        assert _is_sponsored_event(_make_event("የጋዜጣዊ መግለጫ፣ ስለ አዲሱ የፋይናንስ መመሪያ")) is True

    def test_amharic_partner_content_agar_yizet(self):
        assert _is_sponsored_event(_make_event("አጋር ይዘት፡ ዘመናዊ የግብርና ቴክኖሎጂ")) is True
        assert _is_sponsored_event(_make_event("የአጋር ይዘት ለኢንዱስትሪ ልማት")) is True

    def test_amharic_special_discount_liyu_qinash(self):
        assert _is_sponsored_event(_make_event("ልዩ ቅናሽ እስከ 50 በመቶ ቅናሽ ተደረገ")) is True

    def test_amharic_fidel_variations_normalization(self):
        # ሠ normalized to ሰ
        assert _is_sponsored_event(_make_event("ሥፖንሰር የተደረገ የንግድ መድረክ")) is True
        # ዐ normalized to አ
        assert _is_sponsored_event(_make_event("ዐጋር ይዘት፡ የትምህርት እድል")) is True

    def test_amharic_legitimate_news_not_rejected(self):
        # Legitimate Amharic news without ad signals must NOT be rejected
        assert _is_sponsored_event(_make_event(
            "የኢትዮጵያና የኬንያ የሁለትዮሽ የንግድ ግንኙነት ተጠናከረ",
            "ሁለቱ አገራት በድንበር ንግድ ላይ ተወያይተዋል።",
        )) is False
        assert _is_sponsored_event(_make_event(
            "የአፍሪካ ህብረት ስብሰባ በአዲስ አበባ ተጀመረ",
            "የተለያዩ አገራት መሪዎች በመዲናዋ ተገኝተዋል።",
        )) is False
        assert _is_sponsored_event(_make_event(
            "የኢትዮጵያ ብሄራዊ ባንክ አዲስ የገንዘብ ፖሊሲ ይፋ አደረገ",
            "የዋጋ ግሽበትን ለመቆጣጠር ያለመ መመሪያ ነው።",
        )) is False


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

    def test_amharic_blocked_keywords_rejects(self):
        event = _make_event("ማስታወቂያ፡ አዲስ ስልክ ተጀመረ", primary_category="Technology")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["ማስታወቂያ"]}
        assert _passes_bucket_filters(event, cfg) is False

    def test_amharic_blocked_keywords_with_punctuation(self):
        event = _make_event("ኢትዮ፡ቴሌኮም ልዩ ጥቅል", primary_category="Business")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": ["ኢትዮ ቴሌኮም"]}
        assert _passes_bucket_filters(event, cfg) is False

    def test_amharic_allowed_keywords_passes(self):
        event = _make_event("የምርጫ ዝግጅት በአዲስ አበባ ተጠናቀቀ")
        cfg = {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": ["ምርጫ"], "blocked_keywords": []}
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


# ---------------------------------------------------------------------------
# Problem 4: Plan Telegram posts Amharic advertorial exclusion test
# ---------------------------------------------------------------------------

class TestPlanTelegramPostsAmharicFilter:
    """Verify that plan_telegram_posts rejects Amharic advertorials and plans only legitimate news."""

    def test_plan_telegram_posts_rejects_amharic_ads(self):
        """Events with Amharic ad signals are excluded from candidate selection and never planned."""
        ad_event_1 = SimpleNamespace(
            id=uuid.uuid4(),
            title="ማስታወቂያ፡ ታላቅ የቤት ሽያጭ በአዲስ አበባ",
            summary="ልዩ ማስታወቂያ ለደንበኞች",
            primary_category="Business",
            primary_region="Addis Ababa",
            trend_score=9.5,
            last_seen_at=datetime.now(UTC),
            review_required=False,
            auto_publish_eligible=True,
        )
        ad_event_2 = SimpleNamespace(
            id=uuid.uuid4(),
            title="ኢትዮ ቴሌኮም ልዩ ቅናሽ ለአዲሱ ዓመት ይፋ አደረገ",
            summary="ቴሌብር ተጠቃሚዎች የቅናሽ ተጠቃሚ እንዲሆኑ ተጋብዘዋል",
            primary_category="Business",
            primary_region="Addis Ababa",
            trend_score=9.0,
            last_seen_at=datetime.now(UTC),
            review_required=False,
            auto_publish_eligible=True,
        )
        ad_event_3 = SimpleNamespace(
            id=uuid.uuid4(),
            title="ስፖንሰር የተደረገ፡ የንግድ ድርጅቶች መድረክ",
            summary="ስፖንሰር የተደረገ ይዘት",
            primary_category="Economy",
            primary_region="Addis Ababa",
            trend_score=8.5,
            last_seen_at=datetime.now(UTC),
            review_required=False,
            auto_publish_eligible=True,
        )
        ad_event_4 = SimpleNamespace(
            id=uuid.uuid4(),
            title="የጋዜጣዊ መግለጫ ስለ አዲሱ የፋይናንስ አገልግሎት",
            summary="ጋዜጣዊ መግለጫ",
            primary_category="Economy",
            primary_region="Addis Ababa",
            trend_score=8.0,
            last_seen_at=datetime.now(UTC),
            review_required=False,
            auto_publish_eligible=True,
        )
        legit_event = SimpleNamespace(
            id=uuid.uuid4(),
            title="የኢትዮጵያና የኬንያ የሁለትዮሽ የንግድ ግንኙነት ተጠናከረ",
            summary="ሁለቱ አገራት በድንበር ንግድና የጸጥታ ትብብር ላይ ተወያይተዋል።",
            primary_category="Politics",
            primary_region="Addis Ababa",
            trend_score=7.0,
            last_seen_at=datetime.now(UTC),
            review_required=False,
            auto_publish_eligible=True,
        )

        class FakePolicy:
            enabled = True
            dry_run = False
            timezone = "Africa/Addis_Ababa"
            posts_per_day = 3
            ethiopia_posts_per_day = 2
            international_posts_per_day = 0
            channel_username = "@Ethiopantimes"
            posting_hours = [8, 14]
            highlight_color = "#00F0FF"
            freshness_hours = 36
            bypass_freshness_for_breaking = True
            content_filters = {
                "ethiopia": {"allowed_categories": [], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}
            }

        fake_policy = FakePolicy()
        added_posts = []

        session = MagicMock()
        session.get.return_value = fake_policy

        candidate_batch = [ad_event_1, ad_event_2, ad_event_3, ad_event_4, legit_event]
        mock_scalars = MagicMock()
        mock_scalars.return_value.all.side_effect = [
            [],  # today_posts
            [],  # already_event_ids
            list(candidate_batch),  # candidates tier 1 (36h)
            list(candidate_batch),  # candidates tier 2 (72h fallback)
            list(candidate_batch),  # candidates tier 3 (168h fallback)
        ]
        mock_scalars.return_value.first.return_value = None
        session.scalars.side_effect = mock_scalars

        def mock_add(obj):
            added_posts.append(obj)
        session.add.side_effect = mock_add

        with patch("app.workers.tasks.SessionLocal", return_value=session), \
             patch("app.services.social.image_pipeline.ImagePipeline") as mock_img_pipe:
            mock_img_pipe.return_value.browse_photos.return_value.items = []
            session.__enter__ = MagicMock(return_value=session)
            session.__exit__ = MagicMock(return_value=False)

            result = plan_telegram_posts()

        # The 4 Amharic advertorials MUST have been filtered out.
        # Only the legitimate event should be planned!
        assert result["planned"] == 1
        assert len(added_posts) == 1
        planned_post = added_posts[0]
        assert planned_post.event_id == legit_event.id
        assert planned_post.event_id not in {ad_event_1.id, ad_event_2.id, ad_event_3.id, ad_event_4.id}


class TestSelectedCategoryFiltering:
    """Verify that when a user selects certain categories, ONLY content of those categories is allowed."""

    def test_sports_filter_allows_sports_and_blocks_others(self):
        sports_en = _make_event("Haaland scores twice as Man City beats Chelsea in Premier League", primary_category="general")
        sports_am = _make_event("የኢትዮጵያ ቡና እና ቅዱስ ጊዮርጊስ የደርቢ እግር ኳስ ጨዋታ", primary_category="general")
        politics_event = _make_event("Parliament passes new electoral bill in emergency session", primary_category="Politics")
        business_event = _make_event("National Bank of Ethiopia raises interest rates to 15%", primary_category="Business")
        general_event = _make_event("Road construction completed in Addis Ababa Bole subcity", primary_category="general")

        cfg = {"allowed_categories": ["sports"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}

        assert _passes_bucket_filters(sports_en, cfg) is True
        assert _passes_bucket_filters(sports_am, cfg) is True
        assert _passes_bucket_filters(politics_event, cfg) is False
        assert _passes_bucket_filters(business_event, cfg) is False
        assert _passes_bucket_filters(general_event, cfg) is False

    def test_politics_filter_allows_politics_and_blocks_sports(self):
        politics_en = _make_event("Prime Minister announces new diplomatic initiative with neighboring states", primary_category="general")
        politics_am = _make_event("ጠቅላይ ሚኒስትሩ አዳዲስ ሚኒስትሮችን በፓርላማ ሾሙ", primary_category="general")
        sports_event = _make_event("Arsenal wins 3-0 against Tottenham in north London derby", primary_category="sports")
        business_event = _make_event("Commercial Bank of Ethiopia reports profit surge", primary_category="business")

        cfg = {"allowed_categories": ["politics"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}

        assert _passes_bucket_filters(politics_en, cfg) is True
        assert _passes_bucket_filters(politics_am, cfg) is True
        assert _passes_bucket_filters(sports_event, cfg) is False
        assert _passes_bucket_filters(business_event, cfg) is False

    def test_multiple_categories_allowed(self):
        sports_event = _make_event("Athletics federation announces team for world championship marathon", primary_category="general")
        politics_event = _make_event("Council of Ministers ratifies bilateral trade treaty", primary_category="general")
        tech_event = _make_event("New AI startup launches cloud database service", primary_category="technology")

        cfg = {"allowed_categories": ["sports", "politics"], "blocked_categories": [], "allowed_keywords": [], "blocked_keywords": []}

        assert _passes_bucket_filters(sports_event, cfg) is True
        assert _passes_bucket_filters(politics_event, cfg) is True
        assert _passes_bucket_filters(tech_event, cfg) is False

