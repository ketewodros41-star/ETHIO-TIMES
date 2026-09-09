"""Claim extraction: Gemini path + deterministic fallback."""

from __future__ import annotations

from app.models.article import ArticleAnalysis
from app.services.intelligence.claim_extraction import ClaimExtractionService

from tests.factories import make_article, make_source
from tests.fakes import FakeAIProvider


def test_extract_via_provider(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="NBE raises policy rate",
        summary="The National Bank of Ethiopia raised the policy rate.",
        content="NBE raised the policy rate to 15 percent in Addis Ababa.",
    )
    bundle = ClaimExtractionService(FakeAIProvider()).extract_for_article(article)
    assert bundle.used_fallback is False
    assert bundle.result.claims[0].claim_type == "financial"
    assert "National Bank of Ethiopia" in bundle.result.cited_institutions
    assert bundle.result.claims[0].excerpt


def test_fallback_extracts_casualty_and_money(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session,
        source,
        title="Clashes in Oromia",
        summary="12 people killed near the border. Losses of 2 billion birr reported.",
        content="Officials said 12 people killed. Damages of 2 billion birr. Addis Ababa briefing.",
    )
    bundle = ClaimExtractionService(
        FakeAIProvider(available=False)
    ).extract_for_article(article)
    assert bundle.used_fallback is True
    types = {c.claim_type for c in bundle.result.claims}
    assert "casualty" in types
    assert "financial" in types or "statistical" in types
    assert any(c.normalized_value == "12" for c in bundle.result.claims)
    casualty = next(c for c in bundle.result.claims if c.claim_type == "casualty")
    assert casualty.excerpt


def test_fallback_uses_article_analysis_money(db_session):
    source = make_source(db_session)
    article = make_article(
        db_session, source, title="Budget", summary="Ministry of Finance statement"
    )
    article.analysis = ArticleAnalysis(
        article_id=article.id,
        category="economy",
        money=[{"amount": "4.5", "currency": "%", "context": "inflation at 4.5%"}],
        statistics=[],
        dates=[],
        entities={"government_institutions": ["Ministry of Finance"]},
        entity_names=["ministry of finance"],
        topics=["economy"],
    )
    db_session.flush()
    bundle = ClaimExtractionService(
        FakeAIProvider(available=False)
    ).extract_for_article(article)
    assert any(c.claim_type == "financial" for c in bundle.result.claims)
    assert any("Ministry of Finance" in i for i in bundle.result.cited_institutions)
