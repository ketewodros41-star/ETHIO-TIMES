"""AgentRouter AI text provider implementation.

Implements structured-JSON text generation behind the ``AIProvider``
interface using AgentRouter (https://agentrouter.org/) with models such
as deepseek-v4-flash or claude-opus-4-8.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProvider,
    ProviderNotConfiguredError,
    ProviderResponseError,
    RateLimitError,
    TextGenerationRequest,
)

logger = get_logger(__name__)


def _extract_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        obj_match = re.search(r"(\{[\s\S]*\})", text)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except json.JSONDecodeError:
                pass
        raise ProviderResponseError(f"Failed to parse JSON response: {text[:200]}") from exc


class AgentRouterTextProvider(AIProvider):
    name: str = "agent-router"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "agent_router_key", None)
        self.model = model or getattr(settings, "agent_router_model", "deepseek-v4-flash")
        self.base_url = base_url or "https://agentrouter.org/v1"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, request: TextGenerationRequest) -> dict[str, Any]:
        if not self.is_available():
            raise ProviderNotConfiguredError("AgentRouter API key not configured")

        system_content = (
            request.system
            or "You are an expert news analyst and visual director. Respond ONLY with a valid, parseable JSON object."
        )
        if request.response_schema:
            schema_str = json.dumps(request.response_schema)
            system_content += f"\nYour response must strictly conform to this JSON schema (output ONLY the JSON instance, no markdown, no explanations):\n{schema_str}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Cline/2.0.0",
            "Accept": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature if request.temperature is not None else 0.1,
            "max_tokens": request.max_tokens or 2048,
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if res.status_code == 429:
                    raise RateLimitError("AgentRouter rate limit exceeded")
                if res.status_code != 200:
                    raise ProviderResponseError(f"AgentRouter API error {res.status_code}: {res.text[:300]}")

                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_json_block(content)
        except (RateLimitError, ProviderResponseError):
            raise
        except Exception as exc:
            raise ProviderResponseError(f"AgentRouter API call failed: {exc}") from exc

    def embed(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        return []
