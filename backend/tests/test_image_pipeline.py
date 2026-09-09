from __future__ import annotations

import pytest
from app.integrations.ai.mock_image import MockImageProvider
from app.models.enums import ContentFormat, InstagramPostFormat
from app.models.news_event import NewsEvent
from app.services.social.editorial_engine import EditorialBrief
from app.services.social.image_pipeline import ImagePipeline
from tests.fakes import FakeAIProvider


def test_image_pipeline(db_session):
    text_provider = FakeAIProvider(available=False)
    image_provider = MockImageProvider()
    pipeline = ImagePipeline(db_session, text_provider, image_provider)

    event = NewsEvent(title="Test Event", summary="Summary")
    db_session.add(event)
    db_session.flush()

    brief = EditorialBrief(
        headline="H",
        subheadline=None,
        short_summary="S",
        full_summary="F",
        why_it_matters="W",
        key_facts=[],
        what_happens_next=None,
        instagram_caption="",
        hashtags=[],
        source_attribution="",
        suggested_theme="",
        suggested_format=InstagramPostFormat.portrait,
        content_format=ContentFormat.single_image_post,
    )

    res = pipeline.run(event, brief)
    assert res.selected_asset is not None
    assert res.selected_asset.status.value == "generated"

