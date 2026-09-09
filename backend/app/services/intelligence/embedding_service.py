"""Embedding generation + persistence (Phase 2).

Uses the Gemini ``gemini-embedding-001`` model at a configurable dimensionality
(default 1536, L2-normalized in the provider) and stores the vector on the
article via pgvector. Nearest-neighbor search is exposed by the repositories.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.ai.base import AIProvider, ProviderNotConfiguredError
from app.models.article import Article

logger = get_logger(__name__)


def build_embedding_text(article: Article) -> str:
    parts = [article.title or "", article.summary or "", (article.content or "")[:4000]]
    text = "\n".join(p for p in parts if p).strip()
    return text


class EmbeddingService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def embed_article(self, article: Article) -> bool:
        """Generate + persist an embedding for the article. Returns success."""
        if not self.provider.is_available():
            raise ProviderNotConfiguredError(
                "Embedding provider not configured (GEMINI_API_KEY missing)"
            )
        text = build_embedding_text(article)
        if not text:
            logger.info("embedding_skipped_empty", article_id=str(article.id))
            return False

        vectors = self.provider.embed([text], task_type="RETRIEVAL_DOCUMENT")
        if not vectors:
            return False
        vector = vectors[0]
        if len(vector) != settings.embedding_dim:
            logger.warning(
                "embedding_dim_mismatch",
                got=len(vector),
                expected=settings.embedding_dim,
            )
        article.embedding = vector
        article.embedding_model = settings.gemini_embedding_model
        article.embedded_at = datetime.now(UTC)
        return True
