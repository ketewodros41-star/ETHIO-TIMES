"""Sensitive-news rules: politics/conflict never auto-publish."""

from __future__ import annotations

from app.models.news_event import NewsEvent
from app.services.intelligence.sensitive_rules import evaluate_sensitive

from tests.factories import make_article, make_source


def test_politics_is_sensitive(db_session):
    event = NewsEvent(title="Cabinet reshuffle", primary_category="politics")
    db_session.add(event)
    db_session.flush()
    src = make_source(db_session)
    article = make_article(db_session, src, title="PM announces cabinet")
    verdict = evaluate_sensitive(event, [article])
    assert verdict.sensitive is True
    assert "politics" in verdict.categories


def test_casualty_copy_is_sensitive(db_session):
    event = NewsEvent(title="Road accident")
    db_session.add(event)
    db_session.flush()
    src = make_source(db_session)
    article = make_article(
        db_session, src, title="20 killed in bus crash", summary="Deaths confirmed"
    )
    verdict = evaluate_sensitive(event, [article])
    assert verdict.sensitive is True
    assert "deaths" in verdict.categories


def test_benign_economy_item_not_sensitive(db_session):
    event = NewsEvent(
        title="Coffee export volumes rise",
        primary_category="economy",
        categories=["economy"],
        summary="Shipments increased this quarter.",
    )
    db_session.add(event)
    db_session.flush()
    src = make_source(db_session)
    article = make_article(
        db_session,
        src,
        title="Coffee export volumes rise",
        summary="Shipments increased this quarter.",
    )
    verdict = evaluate_sensitive(event, [article])
    assert verdict.sensitive is False
