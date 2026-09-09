"""Application configuration loaded from environment variables.

All secrets come from the environment (see `.env.example`). Nothing sensitive
is ever hard-coded or committed.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    project_name: str = Field(default="ETHIOTIMES")

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+psycopg://ethiotimes:ethiotimes@localhost:5432/ethiotimes"
    )
    database_migration_url: str | None = Field(default=None)

    # ---- Redis / Celery ----
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # ---- Auth ----
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)

    # ---- CORS ----
    cors_origins: str = Field(default="http://localhost:3000")

    # ---- Ingestion ----
    default_crawl_frequency_minutes: int = Field(default=30)
    ingest_http_timeout_seconds: int = Field(default=20)
    ingest_user_agent: str = Field(
        default="ETHIOTIMES-Bot/1.0 (+https://ethiotimes.example)"
    )

    # ---- AI providers (Gemini) ----
    gemini_api_key: str | None = Field(default=None)
    gemini_text_model: str = Field(default="gemini-2.5-flash")
    gemini_image_model: str = Field(default="imagen-3.0")
    gemini_embedding_model: str = Field(default="gemini-embedding-001")
    # gemini-embedding-001 defaults to 3072 dims; 1536 is a recommended MRL
    # truncation that matches the Phase-1 vector column. Truncated dims are NOT
    # auto-normalized by this model, so we L2-normalize in the provider.
    embedding_dim: int = Field(default=1536)
    gemini_request_timeout_seconds: int = Field(default=60)
    gemini_max_retries: int = Field(default=4)
    gemini_retry_base_delay_seconds: float = Field(default=2.0)
    gemini_temperature: float = Field(default=0.2)

    # ---- Intelligence pipeline thresholds ----
    relevance_threshold: int = Field(default=70)  # score >= => relevant
    relevance_borderline_margin: int = Field(default=15)  # [thr-margin, thr) => borderline
    # Cosine similarity bands for clustering (0..1).
    cluster_duplicate_threshold: float = Field(default=0.90)
    cluster_same_event_threshold: float = Field(default=0.80)
    cluster_related_threshold: float = Field(default=0.70)
    # Window (hours) within which two articles can be considered the same event.
    cluster_time_window_hours: int = Field(default=72)
    # Max neighbors to consider when clustering a new article.
    cluster_candidate_limit: int = Field(default=25)
    # Max pipeline attempts before an article is sent to the dead-letter state.
    pipeline_max_attempts: int = Field(default=5)

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sync_migration_url(self) -> str:
        """URL used by Alembic; prefer the direct connection when provided."""
        return self.database_migration_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
