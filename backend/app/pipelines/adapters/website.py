"""Website crawler adapter — Phase 2 stub.

Will crawl article listing pages for sources without an RSS feed (e.g. ENA,
FBC, government sites), extract links, and parse article pages with readability
heuristics. Left as a stub in Phase 1.
"""

from __future__ import annotations

from app.pipelines.adapters.base import BaseSourceAdapter, FetchedItem


class WebsiteCrawlerAdapter(BaseSourceAdapter):
    source_type_label = "website"

    def can_handle(self) -> bool:
        return bool(self.source.base_url)

    def fetch(self) -> list[FetchedItem]:
        raise NotImplementedError(
            "WebsiteCrawlerAdapter is implemented in Phase 2 for RSS-less sources."
        )
