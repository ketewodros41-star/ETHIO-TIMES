"""Editorial importance scoring."""

from __future__ import annotations

from app.models.article import ArticleAnalysis
from app.models.enums import ClaimType
from app.models.news_event import NewsEvent
from app.models.verification import EventClaim
from app.services.intelligence.importance import score_editorial_importance

from tests.factories import make_article, make_source


def test_importance_rises_for_conflict_and_casualties(db_session):
    src = make_source(db_session, slug="imp-src")
    article = make_article(db_session, src, title="Clashes kill 12 in Amhara")
    article.analysis = ArticleAnalysis(
        article_id=article.id,
        category="conflict",
        importance=80,
        entities={"people": ["Abiy Ahmed"], "government_institutions": ["ENDF"]},
        entity_names=["Abiy Ahmed", "ENDF", "Amhara"],
        topics=["conflict", "casualties"],
    )
    db_session.flush()
    event = NewsEvent(
        title="Clashes kill 12 in Amhara",
        primary_category="conflict",
        key_entities=["Amhara", "ENDF"],
        verification_score=40,
        primary_source_available=False,
    )
    quiet = NewsEvent(
        title="Football friendly in Addis",
        primary_category="sports",
        key_entities=[],
        verification_score=10,
    )
    sports = make_article(db_session, src, title="Football friendly in Addis")
    sports.analysis = ArticleAnalysis(
        article_id=sports.id,
        category="sports",
        importance=30,
        entities={},
        entity_names=[],
        topics=["sports"],
    )
    db_session.flush()
    claim = EventClaim(
        claim_text="12 killed",
        claim_type=ClaimType.casualty,
        is_major=True,
        confidence=0.8,
    )
    high, high_detail = score_editorial_importance(event, [article], [claim])
    low, _ = score_editorial_importance(quiet, [sports], [])
    assert high > low
    assert high >= 70
    assert high_detail["casualty_claims"] is True
