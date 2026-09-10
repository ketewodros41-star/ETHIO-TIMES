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
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")

    # ---- Ingestion ----
    default_crawl_frequency_minutes: int = Field(default=30)
    ingest_http_timeout_seconds: int = Field(default=20)
    ingest_user_agent: str = Field(
        default="ETHIOTIMES-Bot/1.0 (+https://ethiotimes.example)"
    )

    # ---- AI providers (Gemini & NVIDIA) ----
    gemini_api_key: str | None = Field(default=None)
    gemini_text_model: str = Field(default="gemini-2.5-flash")
    gemini_image_model: str = Field(default="imagen-3.0")
    gemini_embedding_model: str = Field(default="gemini-embedding-001")
    nvidia_api_key: str | None = Field(default=None)
    pexels_api_key: str = ""
    nvidia_text_model: str = Field(default="meta/llama-3.2-11b-vision-instruct")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1")
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

    # ---- Verification (Phase 3) ----
    verification_max_attempts: int = Field(default=5)
    verification_confirmed_min_score: int = Field(default=75)
    verification_partial_min_score: int = Field(default=50)
    verification_developing_min_score: int = Field(default=30)
    verification_auto_publish_min_score: int = Field(default=80)
    verification_max_articles_for_llm: int = Field(default=8)

    # ---- Trend intelligence (Phase 4) ----
    # Weights must sum to 1.0. Component scores are 0–100 before weighting.
    trend_recency_weight: float = Field(default=0.20)
    trend_velocity_weight: float = Field(default=0.20)
    trend_diversity_weight: float = Field(default=0.15)
    trend_public_impact_weight: float = Field(default=0.20)
    trend_social_momentum_weight: float = Field(default=0.10)
    trend_search_interest_weight: float = Field(default=0.10)
    trend_editorial_importance_weight: float = Field(default=0.05)
    trend_status_emerging_min: float = Field(default=40.0)
    trend_status_trending_min: float = Field(default=60.0)
    trend_status_high_priority_min: float = Field(default=80.0)
    trend_breaking_min_score: float = Field(default=65.0)
    trend_breaking_min_articles_1h: int = Field(default=3)
    trend_breaking_min_sources_1h: int = Field(default=2)
    trend_breaking_min_growth: float = Field(default=3.0)
    trend_stale_minutes: int = Field(default=15)
    trend_skip_fresh_seconds: int = Field(default=120)

    # ---- Instagram Graph API (Phase 5) ----
    instagram_access_token: str | None = Field(default=None)
    instagram_business_account_id: str | None = Field(default=None)

    # ---- Media / Playwright render (Phase 5) ----
    media_root: str = Field(default="./media")
    next_public_url: str = Field(default="http://localhost:3000")
    playwright_timeout_ms: int = Field(default=15_000)
    mock_render: bool = Field(default=False)

    # ---- Image generation (Phase 5) ----
    max_image_retries: int = Field(default=2)
    image_quality_threshold: int = Field(default=75)
    image_candidates_per_event: int = Field(default=2)
    image_provider_preference: str = Field(default="flux")  # "flux" | "together" | "openrouter"

    # ---- External Model Providers ----
    openrouter_api_key: str | None = Field(default=None)
    together_api_key: str | None = Field(default=None)
    agent_router_key: str | None = Field(default=None, alias="AGENT_ROUTER")
    agent_router_model: str = Field(default="deepseek-v4-flash")

    # ---- Editorial (Phase 5) ----
    caption_max_chars: int = Field(default=2200)
    editorial_min_verification_score: int = Field(default=50)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

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
