"""Contradiction detection: heuristic numeric conflicts + Gemini pairs."""

from __future__ import annotations

from app.models.enums import ClaimType, ContradictionSeverity
from app.models.news_event import NewsEvent
from app.models.verification import Contradiction, EventClaim
from app.services.intelligence.contradiction_service import ContradictionService
from sqlalchemy import select

from tests.factories import make_article, make_source
from tests.fakes import FakeAIProvider


def _claim(event, article, *, text, ctype, value) -> EventClaim:  # noqa: ANN001
    kind = "casualty" if ctype == ClaimType.casualty else "num"
    return EventClaim(
        event_id=event.id,
        article_id=article.id,
        claim_text=text,
        claim_type=ctype,
        normalized_value=value,
        entities=["incident"],
        canonical_key=f"{ctype.value}:incident:{kind}",
        confidence=0.8,
        is_major=True,
    )


def test_heuristic_casualty_conflict_is_critical(db_session):
    src_a = make_source(db_session, slug="a")
    src_b = make_source(db_session, slug="b")
    a1 = make_article(db_session, src_a, title="12 killed")
    a2 = make_article(db_session, src_b, title="3 killed")
    event = NewsEvent(title="Clash")
    db_session.add(event)
    db_session.flush()
    c1 = _claim(event, a1, text="12 people killed", ctype=ClaimType.casualty, value="12")
    c2 = _claim(event, a2, text="3 people killed", ctype=ClaimType.casualty, value="3")
    db_session.add_all([c1, c2])
    db_session.flush()

    svc = ContradictionService(db_session, FakeAIProvider(available=False))
    found = svc.detect(event.id, [c1, c2])
    assert len(found) == 1
    assert found[0].severity == ContradictionSeverity.critical
    rows = list(
        db_session.scalars(
            select(Contradiction).where(Contradiction.event_id == event.id)
        )
    )
    assert len(rows) == 1


def test_gemini_contradiction_persisted(db_session):
    src_a = make_source(db_session, slug="ga")
    src_b = make_source(db_session, slug="gb")
    a1 = make_article(db_session, src_a, title="rate 15")
    a2 = make_article(db_session, src_b, title="rate 10")
    event = NewsEvent(title="NBE rate")
    db_session.add(event)
    db_session.flush()
    c1 = _claim(event, a1, text="rate 15%", ctype=ClaimType.financial, value="15%")
    c2 = _claim(event, a2, text="rate 10%", ctype=ClaimType.financial, value="10%")
    db_session.add_all([c1, c2])
    db_session.flush()

    provider = FakeAIProvider(
        contradictions={
            "contradictions": [
                {
                    "claim_a_index": 0,
                    "claim_b_index": 1,
                    "description": "Policy rate figures disagree",
                    "severity": "high",
                }
            ]
        }
    )
    found = ContradictionService(db_session, provider).detect(event.id, [c1, c2])
    assert any(x.severity == ContradictionSeverity.high for x in found)
    assert "contradictions" in provider.calls
