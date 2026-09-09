import pytest
from app.services.social.render_service import RenderService
from app.models.social_post import SocialPost
from app.models.enums import InstagramPostFormat
from app.core.config import settings

def test_mock_render():
    settings.mock_render = True
    svc = RenderService()
    post = SocialPost(id="123e4567-e89b-12d3-a456-426614174000", format=InstagramPostFormat.portrait)
    path = svc.render_post(post)
    assert path.exists()
    assert b"PNG" in path.read_bytes()
