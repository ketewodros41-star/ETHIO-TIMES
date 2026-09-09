"""API source adapter — Phase 2+ stub.

For sources exposing a JSON/REST or licensed wire API (e.g. Reuters, AP). Left
as a stub in Phase 1.
"""

from __future__ import annotations

from app.pipelines.adapters.base import BaseSourceAdapter, FetchedItem


class APISourceAdapter(BaseSourceAdapter):
    source_type_label = "api"

    def can_handle(self) -> bool:
        return bool(self.source.api_url)

    def fetch(self) -> list[FetchedItem]:
        raise NotImplementedError(
            "APISourceAdapter is implemented in a later phase for licensed APIs."
        )
