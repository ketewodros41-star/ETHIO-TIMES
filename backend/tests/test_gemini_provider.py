"""Tests for the Gemini provider using a mocked SDK client (no network)."""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.integrations.ai.base import (
    ProviderResponseError,
    RateLimitError,
    TextGenerationRequest,
)
from app.integrations.ai.gemini import GeminiTextProvider, _l2_normalize


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    # Keep retry-driven tests fast and deterministic.
    monkeypatch.setattr(settings, "gemini_max_retries", 1)
    monkeypatch.setattr(settings, "gemini_retry_base_delay_seconds", 0)


class _Resp:
    def __init__(self, text):
        self.text = text


class _EmbVal:
    def __init__(self, values):
        self.values = values


class _EmbResp:
    def __init__(self, vectors):
        self.embeddings = [_EmbVal(v) for v in vectors]


class _Models:
    def __init__(self, *, gen=None, emb=None, raise_exc=None):
        self._gen = gen
        self._emb = emb
        self._raise = raise_exc

    def generate_content(self, **kwargs):
        if self._raise:
            raise self._raise
        return self._gen

    def embed_content(self, **kwargs):
        if self._raise:
            raise self._raise
        return self._emb


class _Client:
    def __init__(self, models):
        self.models = models


def _provider(models) -> GeminiTextProvider:
    p = GeminiTextProvider(api_key="test-key")
    p._client = _Client(models)  # inject mock; bypass real SDK client
    return p


def test_l2_normalize_unit_length():
    v = _l2_normalize([3.0, 4.0])
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9


def test_generate_json_parses_valid_json():
    p = _provider(_Models(gen=_Resp('{"score": 90, "ok": true}')))
    out = p.generate_json(TextGenerationRequest(prompt="hi"))
    assert out == {"score": 90, "ok": True}


def test_generate_json_non_json_raises():
    p = _provider(_Models(gen=_Resp("not json {")))
    with pytest.raises(ProviderResponseError):
        p.generate_json(TextGenerationRequest(prompt="hi"))


def test_generate_json_empty_raises():
    p = _provider(_Models(gen=_Resp("")))
    with pytest.raises(ProviderResponseError):
        p.generate_json(TextGenerationRequest(prompt="hi"))


def test_generate_json_rate_limit_mapped():
    p = _provider(_Models(raise_exc=Exception("429 RESOURCE_EXHAUSTED")))
    with pytest.raises(RateLimitError):
        p.generate_json(TextGenerationRequest(prompt="hi"))


def test_embed_normalizes_vectors():
    p = _provider(_Models(emb=_EmbResp([[3.0, 4.0]])))
    out = p.embed(["hello"])
    assert len(out) == 1
    assert abs(sum(x * x for x in out[0]) - 1.0) < 1e-9


def test_embed_empty_input_short_circuits():
    p = _provider(_Models())
    assert p.embed([]) == []


def test_not_available_without_key():
    assert GeminiTextProvider(api_key=None).is_available() is False
