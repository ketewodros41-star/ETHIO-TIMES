"""Primary-source discovery MVP against the official registry."""

from __future__ import annotations

from app.models.enums import SourceType
from app.models.news_event import EventTimeline, NewsEvent
from app.services.intelligence.primary_source import PrimarySourceService
from sqlalchemy import select

from tests.factories import make_article, make_source


def test_discovers_nbe_from_secondary_citation(db_session):
    nbe = make_source(
        db_session,
        slug="nbe-ethiopia",
        name="National Bank of Ethiopia (NBE)",
        source_type=SourceType.financial_institution,
        is_primary_source=True,
        trust_profile={"tier": 1, "type": "primary_official"},
    )
    outlet = make_source(db_session, slug="addis-standard", name="Addis Standard")
    article = make_article(
        db_session,
        outlet,
        title="NBE raises rates",
        summary="The National Bank of Ethiopia announced a policy rate hike.",
        content="According to the National Bank of Ethiopia, the policy rate rose.",
    )
    event = NewsEvent(title="NBE raises rates")
    db_session.add(event)
    db_session.flush()

    discovery = PrimarySourceService(db_session).discover(
        event_id=event.id,
        articles=[article],
        cited_institutions=["National Bank of Ethiopia"],
    )
    assert discovery.available is True
    assert str(nbe.id) in discovery.matched_source_ids
    titles = list(
        db_session.scalars(
            select(EventTimeline.title).where(EventTimeline.event_id == event.id)
        )
    )
    assert any(t and "Primary source" in t for t in titles)


def test_member_primary_source_counts(db_session):
    nbe = make_source(
        db_session,
        slug="nbe-ethiopia",
        name="National Bank of Ethiopia (NBE)",
        source_type=SourceType.financial_institution,
        is_primary_source=True,
    )
    article = make_article(db_session, nbe, title="Policy statement")
    article.source = nbe
    event = NewsEvent(title="Policy statement")
    db_session.add(event)
    db_session.flush()
    discovery = PrimarySourceService(db_session).discover(
        event_id=event.id, articles=[article], cited_institutions=[]
    )
    assert discovery.available is True
    assert discovery.via_member_article is True


def test_business_copy_does_not_false_match_ess(db_session):
    make_source(
        db_session,
        slug="ess-ethiopia",
        name="Ethiopian Statistics Service (ESS)",
        source_type=SourceType.research_institution,
        is_primary_source=True,
    )
    outlet = make_source(db_session, slug="capital", name="Capital")
    article = make_article(
        db_session,
        outlet,
        title="Business Ethiopia expansion",
        summary="A business Ethiopia briefing on coffee exports.",
        content="The business Ethiopia community welcomed the deal.",
    )
    event = NewsEvent(title="Coffee exports")
    db_session.add(event)
    db_session.flush()
    discovery = PrimarySourceService(db_session).discover(
        event_id=event.id, articles=[article], cited_institutions=[]
    )
    assert discovery.available is False
