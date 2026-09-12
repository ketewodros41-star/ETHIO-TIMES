"""Unit tests for analysis: structured parsing + deterministic fallback."""

from __future__ import annotations

from app.services.intelligence.analysis_service import AnalysisService, detect_language

from tests.fakes import FakeAIProvider


def test_detect_language_ethiopic_is_amharic():
    assert detect_language("የኢትዮጵያ ዜና ዛሬ") == "am"


def test_detect_language_english():
    assert detect_language("Ethiopia announces new economic policy in Addis Ababa") == "en"


def test_detect_language_english_with_an_amharic_name_is_not_amharic():
    assert detect_language("Ethiopia announces policy, according to \u12a0\u1262\u12ed \u12a0\u1205\u1218\u12f5.") == "en"


def test_detect_language_empty():
    assert detect_language("") == "und"


def test_analysis_via_provider_parses_entities():
    svc = AnalysisService(FakeAIProvider())
    result, used_fallback = svc.analyze(
        title="PM statement", summary="Ethiopia policy", content=None
    )
    assert used_fallback is False
    assert result.category == "politics"
    assert "Ethiopia" in result.entities.countries
    assert result.importance == 72
    assert "ethiopia" in result.entities.all_names()


def test_analysis_fallback_detects_language():
    svc = AnalysisService(FakeAIProvider(available=False))
    result, used_fallback = svc.analyze(
        title="Ethiopia raises interest rates", summary=None, content=None
    )
    assert used_fallback is True
    assert result.language == "en"
    assert result.category == "general"
