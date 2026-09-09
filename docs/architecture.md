# ETHIOTIMES — Architecture

ETHIOTIMES is an **Ethiopian News Intelligence Engine** with automated,
multi-channel social publishing. The intelligence layer (sourcing, ingestion,
clustering, verification, analysis) is the product; Instagram/Telegram/X/etc. are
distribution channels.

This document describes the Phase 1 foundation and how later phases attach to it.

## System overview

```
                       ┌─────────────────────────────┐
                       │        Next.js dashboard     │  (dark newsroom UI)
                       │  sources · articles · health │
                       └───────────────┬─────────────┘
                                       │ REST (/api/v1)
                       ┌───────────────▼─────────────┐
                       │         FastAPI API          │
                       │  auth · sources · articles   │
                       │  health · ingest (enqueue)   │
                       └───────┬───────────────┬──────┘
                               │               │ enqueue only
             SQLAlchemy /      │               │
             Alembic           │        ┌──────▼───────┐   Redis broker
                       ┌───────▼──────┐ │ Celery beat  │◄──────────────┐
                       │  PostgreSQL  │ │  (schedule)  │               │
                       │  + pgvector  │ └──────┬───────┘        ┌──────▼──────┐
                       │  (Supabase)  │        │ enqueue        │   Celery    │
                       └───────▲──────┘        └───────────────►│   workers   │
                               │                                │ (ingestion) │
                               └────────── read/write ──────────┴─────────────┘
                                                       │
                                        ┌──────────────▼──────────────┐
                                        │   Source adapters            │
                                        │   RSS ✓ · Website ⋯ · API ⋯  │
                                        │   Telegram ⋯                 │
                                        └──────────────────────────────┘
```

`✓` implemented in Phase 1. `⋯` stub for a later phase.

> **Phase 2 (Intelligence) is now implemented.** On top of ingestion, articles
> flow through a Gemini-powered pipeline: relevance → analysis → embedding →
> clustering into events. See [Intelligence pipeline (Phase 2)](#intelligence-pipeline-phase-2).

## Backend domain layout

```
backend/app/
  api/            # FastAPI routers + dependencies
  core/           # config, logging, security
  db/             # engine, session, declarative base
  models/         # SQLAlchemy ORM models + enums
  schemas/        # Pydantic request/response models
  repositories/   # data-access layer (queries)
  services/       # business logic / orchestration
  pipelines/      # ingestion adapters, normalization, relevance
  workers/        # Celery app, beat schedule, tasks
  integrations/   # external provider abstractions (AI, images, ...)
  data/           # seed data (Ethiopian source registry)
```

The dependency direction is: `api → services → repositories → models`, with
`pipelines`/`integrations` used by `services`/`workers`. Nothing in `models`
imports upward.

## Data model (Phase 1)

- **news_sources** — the registry ETHIOTIMES monitors (see seed set below).
- **articles** — raw + normalized ingested content, deduped by `canonical_url`,
  with a nullable `embedding vector(1536)` reserved for Phase 2 semantic work.
- **article_versions** — historical snapshots for change tracking.
- **news_events / event_articles** — clustering tables (schema only in Phase 1).
- **pipeline_jobs** — execution records for Celery ingestion tasks.
- **audit_logs** — append-only trail of mutations/system actions.
- **users** — dashboard operators (auth scaffolding).

The `vector` (pgvector) and `pgcrypto` extensions are enabled in migration `0001`.

## Ingestion flow (Phase 1)

1. **Celery beat** runs `poll_due_sources` every 5 minutes.
2. It selects active sources with an `rss_url` that are **due** based on
   `crawl_frequency_minutes` / `last_checked_at`, and enqueues one
   `ingest_source` task per source (isolated failures).
3. `ingest_source` selects an adapter (RSS in Phase 1), fetches + normalizes
   items, **deduplicates by `canonical_url`**, computes an Ethiopia-relevance
   keyword score, and persists new `articles`.
4. Source **health** is updated (success/degraded/failing) and a `pipeline_job`
   row records the outcome.

The API's `/ingest/trigger` endpoint **only enqueues**; ingestion never runs in
the request path.

## Source registry & seeding

Migration `0002` seeds ~20 Ethiopian-focused sources across independent media,
business media, national agencies/broadcasters, government/officials, financial
institutions, research institutions, and international media/wires. Real RSS
feeds are used where confident (e.g. WordPress `/feed/`, BBC Africa, Al Jazeera);
sources without a confirmed feed (ENA, FBC, government sites, wires) are seeded
with `rss_url = NULL` and will be handled by the website-crawler / API adapters
in later phases.

### Telegram — Phase 1.5 expansion & impersonation warning

Ethiopian breaking news frequently originates on **Telegram** (e.g. *Tikvah
Ethiopia*). Phase 1 includes the `telegram_channel` source type and a stub
adapter, but **no Telegram ingestion runs yet**.

> ⚠️ **Impersonation warning.** Telegram is rife with impersonation channels.
> ETHIOTIMES must **never** ingest from a channel whose `@handle` has not been
> verified against the outlet's **official website**. Telegram sources are seeded
> with `verification_status = needs_verification`, no fabricated `@handle`, and
> `is_active = false` until a human confirms the handle. Phase 1.5 will add
> verified-channel ingestion via the Telegram API/MTProto or a bot.

## AI provider abstractions

`integrations/ai` defines provider-agnostic `AIProvider` and `ImageProvider`
interfaces plus Gemini stubs. Phase 1 wires configuration only; calling a
provider raises a clear "wired in a later phase" error so no paid API is invoked
accidentally.

## Intelligence pipeline (Phase 2)

Phase 2 turns raw ingested articles into structured intelligence and clusters
them into real-world events.

### Stages

```
collected/normalized ─▶ relevance ─▶ analysis ─▶ embedding ─▶ cluster ─▶ (event)
                           │            │            │            │
                     Gemini+keyword  Gemini+lang   Gemini      vector NN +
                       fallback      fallback    embeddings   entities/time/geo
```

Each stage is **idempotent** and guarded by the article's persisted
`processing_status` (`pending → relevance_scored → analyzed → embedded →
clustered`; off-ramps `skipped_irrelevant`, `failed`, `dead_letter`). A single
`process_article` Celery task advances an article through every doable stage and
resumes safely if re-run.

1. **Relevance** (`RelevanceService`) — Gemini returns
   `{is_ethiopia_related, score 0-100, primary_region, reason, categories}`
   (validated by Pydantic). A configurable threshold (`RELEVANCE_THRESHOLD`,
   default 70) with a borderline margin classifies each item as
   relevant / borderline / irrelevant; **borderline items are stored** (not
   discarded). If Gemini is unavailable/invalid, a deterministic keyword
   heuristic is used instead.
2. **Analysis** (`AnalysisService`) — language detection (English, Amharic via
   Ge'ez script detection, Afaan Oromo, and others), category/subcategory,
   entities (people, organizations, companies, government institutions,
   countries/regions/cities), extracted dates/money/statistics, topics, and
   editorial importance. Stored in the `article_analysis` table.
3. **Embedding** (`EmbeddingService`) — `gemini-embedding-001` at
   `EMBEDDING_DIM` (1536), **L2-normalized** (the model does not auto-normalize
   truncated dims), persisted to `articles.embedding` (pgvector), indexed with
   HNSW `vector_cosine_ops`.
4. **Clustering** (`ClusteringService`) — for each embedded article, cosine
   nearest neighbors within `CLUSTER_TIME_WINDOW_HOURS` are scored by a
   composite of **vector similarity + entity overlap + topic overlap +
   category/region agreement**. Bands (configurable): `>=0.90` duplicate,
   `0.80–0.90` possible same event (**Gemini confirms borderline pairs only**),
   `0.70–0.80` related. Cross-language coverage clusters via shared embedding
   space + entities.
5. **Event lifecycle** (`EventService`) — assigns the article to an existing
   event or creates one; sets a typed relation (`primary`/`duplicate`/`related`/
   `follow_up`/`context`); maintains `article_count`, `source_count`,
   `first_seen_at`/`last_seen_at`, `key_entities`, centroid embedding, and status
   (`developing → updated → confirmed` as sources accumulate); and appends
   `event_timeline` entries (`first_report`, `source_confirmation`,
   `new_development`).

### Workers, idempotency & failure handling

- `ingest_source` enqueues `process_article` for each newly-created article.
- Beat `poll_pending_articles` (every 2 min) re-enqueues any non-terminal
  articles; when no provider is configured it only advances stages with
  deterministic fallbacks (so it never loops on states requiring the model).
- `process_article` takes a **row-level lock** (`SELECT … FOR UPDATE SKIP
  LOCKED`) so concurrent workers never process the same article.
- Every run writes a `pipeline_jobs` record; failures increment
  `processing_attempts` and set `failed`, escalating to `dead_letter` after
  `PIPELINE_MAX_ATTEMPTS` (an `audit_logs` entry is written on dead-letter).

### Model & cost notes

- **Text model:** `GEMINI_TEXT_MODEL` (default `gemini-2.5-flash`) — chosen for
  low cost/latency on classification + extraction. All calls use
  `response_mime_type=application/json` with a response schema, temperature
  ~0.2, and bounded `max_output_tokens`. Article content is capped (~6k chars)
  to bound token usage.
- **Embedding model:** `gemini-embedding-001` at 1536 dims (recommended MRL
  truncation; requires manual L2 normalization — done in the provider). Default
  model dim is 3072; we intentionally use 1536 to match the pgvector column and
  reduce storage/latency.
- **Cost control:** Gemini is called at most ~2–3 times per *relevant* article
  (relevance + analysis + optional borderline cluster confirmation) plus one
  embedding; irrelevant articles stop after the relevance call. Duplicate/
  related detection is primarily vector math — Gemini confirmation runs **only**
  for the 0.80–0.90 borderline band.
- **Resilience:** configurable timeout, bounded exponential-backoff retries, and
  explicit HTTP 429 → `RateLimitError` mapping. The API key is read from the
  environment and never logged.
- **CI:** no production AI calls — tests use a deterministic `FakeAIProvider`
  and a mocked SDK client.

## Roadmap (phases)

| Phase | Scope |
|-------|-------|
| **1** | Foundation: schema+migrations, source registry, RSS ingestion, Celery scaffolding, dashboard, brand system, provider abstractions. |
| 1.5 | Verified Telegram channel ingestion. |
| **2 (done)** | Gemini provider; Ethiopia relevance detection; article analysis (multilingual entities/facts); embeddings + pgvector cosine search; duplicate detection & event clustering; event lifecycle + timeline; event feed/detail UI. |
| 3 (next) | Verification & trust scoring (cross-source corroboration); deeper editorial analysis & summarization; Website/API + Telegram adapters feeding the pipeline; Visual Director (Gemini/Imagen image generation) behind the existing `ImageProvider`. |
| 4 | Instagram post composition (Playwright render) + publishing. |
| 5–8 | Carousels; Telegram/X/Facebook/TikTok/website distribution; full editorial AI; analytics. |

### What remains for Phase 3

- **Verification & trust:** corroborate events across independent sources; score
  claim confidence; flag single-source / unverified events (the `event_status`
  and `source_count` fields already support this).
- **Editorial synthesis:** generate a neutral event brief/summary and headline
  candidates from clustered coverage.
- **More adapters into the pipeline:** implement the Website crawler, API, and
  (Phase 1.5) Telegram adapters so RSS-less and Telegram-first sources feed the
  same intelligence flow.
- **Visual Director:** implement `ImageProvider` (Gemini/Imagen) to generate the
  Instagram image zone per the brand visual styles.
- **Backfill embeddings** if `EMBEDDING_DIM`/model changes (re-embed + reindex).

## Local development

See the root [`README.md`](../README.md) for setup, including the Supabase
pooler `DATABASE_URL` shape, migrations, and running the API + worker + beat +
dashboard via `docker-compose` or manually.
