import pytest
from app.services.social.caption_builder import CaptionBuilder
from app.services.social.editorial_engine import EditorialBrief
from app.models.enums import InstagramPostFormat, ContentFormat

def test_caption_assembly():
    builder = CaptionBuilder()
    brief = EditorialBrief(
        headline="H1", subheadline=None, short_summary="S1", full_summary="F1",
        why_it_matters="W1", key_facts=["F2"], what_happens_next=None,
        instagram_caption="", hashtags=["#test"], source_attribution="src",
        suggested_theme="theme", suggested_format=InstagramPostFormat.portrait,
        content_format=ContentFormat.single_image_post
    )
    caption = builder.build(brief)
    assert "H1" in caption
    assert "S1" in caption
    assert "• F2" in caption
    assert "#test" in caption
