"""Deterministic fake AI provider for tests (no network / no production calls)."""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.config import settings
from app.integrations.ai.base import (
    AIProvider,
    ProviderResponseError,
    RateLimitError,
    TextGenerationRequest,
)


def deterministic_embedding(text: str, dim: int | None = None) -> list[float]:
    """Bag-of-words hashed embedding, L2-normalized.

    Overlapping tokens produce higher cosine similarity, which lets clustering
    tests exercise real vector math deterministically.
    """
    d = dim or settings.embedding_dim
    vec = [0.0] * d
    for token in text.lower().split():
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % d
        vec[idx] += 1.0
    norm = sum(x * x for x in vec) ** 0.5
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


class FakeAIProvider(AIProvider):
    """Configurable fake provider.

    - ``relevance`` / ``analysis`` / ``cluster`` dicts override the JSON returned
      for the corresponding prompt type.
    - ``available`` toggles ``is_available``.
    - ``raise_on_json`` raises the given exception from ``generate_json``.
    - ``bad_json`` makes ``generate_json`` return malformed data.
    """

    name = "fake"

    def __init__(
        self,
        *,
        available: bool = True,
        relevance: dict | None = None,
        analysis: dict | None = None,
        cluster: dict | None = None,
        claims: dict | None = None,
        contradictions: dict | None = None,
        trend_signals: dict | None = None,
        raise_on_json: Exception | None = None,
        bad_json: bool = False,
    ) -> None:
        self.available = available
        self.relevance = relevance
        self.analysis = analysis
        self.cluster = cluster
        self.claims = claims
        self.contradictions = contradictions
        self.trend_signals = trend_signals
        self.raise_on_json = raise_on_json
        self.bad_json = bad_json
        self.calls: list[str] = []

    def is_available(self) -> bool:
        return self.available

    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        if self.raise_on_json is not None:
            raise self.raise_on_json
        prompt = request.prompt.lower()
        if "assess trend signals for this clustered ethiopian news event" in prompt:
            self.calls.append("trend_signals")
            if self.bad_json:
                raise ProviderResponseError("bad json")
            return self.trend_signals or {
                "public_impact": 70,
                "social_momentum": 55,
                "search_interest": 60,
                "breaking_likely": False,
                "reason": "fake trend signals",
                "affected_scope": "national",
            }
        if "identify pairs of claims that contradict" in prompt:
            self.calls.append("contradictions")
            if self.bad_json:
                return {"contradictions": "nope"}
            return self.contradictions or {"contradictions": []}
        if "extract structured claims" in prompt:
            self.calls.append("claims")
            if self.bad_json:
                raise ProviderResponseError("bad json")
            return self.claims or {
                "claims": [
                    {
                        "claim_text": "The National Bank of Ethiopia raised the policy rate.",
                        "claim_type": "financial",
                        "normalized_value": "15%",
                        "entities": ["National Bank of Ethiopia"],
                        "excerpt": "NBE raised the policy rate to 15 percent",
                        "is_major": True,
                        "confidence": 0.9,
                    }
                ],
                "cited_institutions": ["National Bank of Ethiopia"],
            }
        if "same real-world event" in prompt:
            self.calls.append("cluster")
            if self.bad_json:
                return {"relation": 123}  # invalid -> will validate/normalize
            return self.cluster or {
                "relation": "same_event",
                "confidence": 0.85,
                "reason": "fake",
            }
        if "assess the ethiopia relevance" in prompt:
            self.calls.append("relevance")
            if self.bad_json:
                raise ProviderResponseError("bad json")
            return self.relevance or {
                "is_ethiopia_related": True,
                "score": 88,
                "primary_region": "Addis Ababa",
                "reason": "fake",
                "categories": ["politics"],
            }
        self.calls.append("analysis")
        if self.bad_json:
            raise ProviderResponseError("bad json")
        return self.analysis or {
            "language": "en",
            "language_name": "English",
            "category": "politics",
            "subcategory": "policy",
            "entities": {
                "people": ["Abiy Ahmed"],
                "organizations": ["ENA"],
                "companies": [],
                "government_institutions": ["Office of the Prime Minister"],
                "countries": ["Ethiopia"],
                "regions": ["Oromia"],
                "cities": ["Addis Ababa"],
            },
            "dates": [{"text": "today", "iso": None, "context": "publication"}],
            "money": [],
            "statistics": [],
            "topics": ["policy", "governance"],
            "importance": 72,
            "summary": "fake summary",
        }

    def embed(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        return [deterministic_embedding(t) for t in texts]


class RateLimitedProvider(FakeAIProvider):
    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        raise RateLimitError("429 resource exhausted")

    def embed(self, texts, task_type="RETRIEVAL_DOCUMENT"):  # noqa: ANN001
        raise RateLimitError("429 resource exhausted")
