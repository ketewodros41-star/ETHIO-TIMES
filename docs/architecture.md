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

> **Phase 3 (Verification) is now implemented.** Clustered events run claim
> extraction, evidence mapping, contradiction detection, and a 0–100
> verification score. See [Verification (Phase 3)](#verification-phase-3).

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

## Verification (Phase 3)

Phase 3 sits **after clustering**. A clustered `news_event` is verified
asynchronously; editorial later must only use **evidenced** claims.

```
clustered event ─▶ claims ─▶ evidence ─▶ contradictions ─▶ primary source
                         │         │            │
                   Gemini+regex  excerpts    heuristic+Gemini
                         └──────────┴────────────┴─▶ score 0–100 + status
                                                    + sensitive-news gate
```

`EventStatus` (developing / confirmed / …) remains the **clustering lifecycle**.
Source Telegram-handle `verification_status` is unchanged. Event verification
uses a distinct PostgreSQL enum `event_verification_status`:

`unverified | developing | partially_confirmed | confirmed | contradicted`

Worker processing state is `event_verify_status`:
`pending | verifying | verified | failed | dead_letter`.

### Claims & evidence

`ClaimExtractionService` asks Gemini for structured claims
(`financial / statistical / political / policy / casualty / geographic /
timeline / announcement`) with a verbatim excerpt. Pydantic validates the JSON;
on provider failure a deterministic fallback mines `article_analysis`
money/statistics/dates plus casualty/percent/currency regexes.

`EvidenceMappingService` persists `event_claims` **only** when an excerpt (and
source article URL) can be attached in `claim_evidence`. Claims without evidence
are dropped.

### Contradictions

`ContradictionService` compares claims across sources. A numeric heuristic
flags conflicting casualty counts (critical) and material financial/statistical
deltas (high/medium). Gemini may add/confirm pairs when available. Results live
in `contradictions` with severity `low | medium | high | critical`.

- Any contradiction **disables** `auto_publish_eligible`.
- High/critical conflicts set `review_required` and map verification status to
  `contradicted`.

### Scoring

Weighted 0–100 (see `app/services/intelligence/scoring.py`):

| Component | Weight |
|-----------|--------|
| Source reliability / trust profiles | 25% |
| Independent source count (cap 5) | 20% |
| Primary source available | 15% |
| Source-type / language / domain diversity | 15% |
| Claim consistency | 15% |
| Evidence coverage of major claims | 10% |

Critical contradictions cap the score at 25. Status mapping uses configurable
thresholds (`VERIFICATION_CONFIRMED_MIN_SCORE` default 75, partial 50,
developing 30) plus independent-source floors. The breakdown is stored on
`news_events.verification_explanation` JSON.

### Primary-source discovery (MVP)

When secondary coverage cites an official institution (NBE, MoF, PMO, MFA, EIC,
ESS, …), `PrimarySourceService` searches the **registered** source registry
(`is_primary_source`) by name/slug/alias and attaches a timeline note if found.
A member article already from a primary source also sets
`primary_source_available`. No fabricated articles are created.

### Sensitive-news rules

Politics, conflict, military, deaths, crime, ethnic tension, religion,
elections, public safety, financial panic, and disasters **always** require
human review and **never** auto-publish.

Auto-publish is otherwise conservative: confirmed status, score ≥
`VERIFICATION_AUTO_PUBLISH_MIN_SCORE` (80), no contradictions, not
`review_required`.

### Workers

- `process_article` enqueues `verify_event` after a successful cluster.
- Beat `poll_pending_verifications` (every 2 min) picks up `pending`/`failed`
  events (including events that received new coverage — attaching an article
  resets verification to `pending`).
- `verify_event` takes `SELECT … FOR UPDATE SKIP LOCKED`, is idempotent
  (skips if already verified and `last_seen_at` ≤ `verified_at`), writes
  `pipeline_jobs` (`event_id` set), and dead-letters after
  `VERIFICATION_MAX_ATTEMPTS` with an `audit_logs` row.

### API / UI

`GET /api/v1/events` filters: `verification_status`, `review_required`.
Event detail includes score/status, claims + evidence, contradictions,
`primary_source_available`, and review reasons. The dashboard event feed and
detail pages render these from the real schema (not placeholders).

## Trend intelligence (Phase 4)

Phase 4 sits **after clustering** (and runs again after verification) so the
newsroom can see which events are *moving*, not only which are verified.

```
clustered/verified event
    ├─ event_velocity_metrics (1h / 6h / 24h / 72h)
    ├─ editorial importance (analysis + category + entities + verification)
    ├─ Gemini trend signals (public impact, social, search, breaking_likely)
    │     └─ heuristic fallback on call failure / missing key
    └─ weighted trend_score 0–100 + component JSON + status
```

`EventStatus` remains the clustering lifecycle. Verification statuses are
unchanged. Trend uses a distinct PostgreSQL enum `trend_status`:

`low | emerging | trending | high_priority | breaking`

### Score

Configurable weights (defaults; see `.env.example`):

| Component | Weight |
|-----------|--------|
| Recency (`last_seen_at`) | 20% |
| Source velocity (1h/6h burst + growth) | 20% |
| Source / language / domain diversity | 15% |
| Public impact | 20% |
| Social momentum | 10% |
| Search interest | 10% |
| Editorial importance | 5% |

Each component is 0–100 before weighting. The breakdown is stored on
`news_events.trend_breakdown` JSON. `trend_score` is also copied onto
`significance_score` so older sort surfaces stay trend-aware.

**Public impact, social momentum, search interest, and `breaking_likely`**
are asked of Gemini (`gemini-2.5-flash`, structured JSON) once per rescore.
If the provider is unavailable or the call fails, documented heuristics run
instead (sensitive-category impact, telegram/social source mix, entity
prominence). There is **no live social firehose or Google Trends** in this
phase — those proxies should be replaced later.

### Velocity & breaking

`event_velocity_metrics` upserts one row per window with `article_count`,
`unique_source_count`, `articles_per_hour`, and `growth_rate` (current window
÷ previous equal-length window). Breaking-candidate heuristics:

- ≥ `TREND_BREAKING_MIN_ARTICLES_1H` articles from ≥ `TREND_BREAKING_MIN_SOURCES_1H`
  sources in 1h
- 1h growth rate ≥ `TREND_BREAKING_MIN_GROWTH` with a populated 6h window
- sustained 6h burst (≥ 8 articles / 3 sources)
- Gemini `breaking_likely` **and** velocity component ≥ 50

`breaking` status requires a candidate **and** (`trend_score` ≥
`TREND_BREAKING_MIN_SCORE` or public impact ≥ 70). Otherwise a burst still
flags `breaking_candidate` and maps to `trending` / `emerging`.

### Workers

- `process_article` enqueues `score_event_trend` after a successful cluster
  (alongside `verify_event`).
- `verify_event` enqueues `score_event_trend` after a successful/skipped run
  so verification signals feed editorial importance.
- Beat `poll_stale_trends` (every 5 min) picks up never-scored events, events
  with `last_seen_at` after `trend_scored_at`, or scores older than
  `TREND_STALE_MINUTES`.
- `score_event_trend` takes `SELECT … FOR UPDATE SKIP LOCKED`, is idempotent
  (skips if scored within `TREND_SKIP_FRESH_SECONDS` and no new coverage),
  and writes `pipeline_jobs`.

### API / UI

`GET /api/v1/events` filters: `trend_status`, `breaking`; `sort=last_seen|trend_score`.
Event detail includes `trend_breakdown` and `velocity_metrics`. Overview shows
breaking and trending rails. Pipeline stats expose `by_trend_status` and
`breaking_candidates`.

## Roadmap (phases)

| Phase | Scope |
|-------|-------|
| **1** | Foundation: schema+migrations, source registry, RSS ingestion, Celery scaffolding, dashboard, brand system, provider abstractions. |
| 1.5 | Verified Telegram channel ingestion. |
| **2 (done)** | Gemini provider; Ethiopia relevance detection; article analysis (multilingual entities/facts); embeddings + pgvector cosine search; duplicate detection & event clustering; event lifecycle + timeline; event feed/detail UI. |
| **3 (done)** | Claim extraction; claim–evidence mapping; contradiction detection; verification scoring; primary-source discovery MVP; sensitive-news review gates; verification workers + event feed/detail UI. |
| **4 (done)** | Trend scoring; event velocity; editorial importance; breaking-candidate detection; trend workers + UI. |
| **5 (done)** | Instagram post composition (Playwright render) + publishing. |
| 6–8 | Carousels; Telegram/X/Facebook/TikTok/website distribution; full editorial AI; analytics. |

### What was built in Phase 5

- **Instagram composition:** Playwright render of branded post templates from
  verified/evidenced event briefs (not raw unverified claims).
- **Publishing:** Instagram Graph/content publishing, scheduling, and failure
  handling. Auto-publish must honour `auto_publish_eligible` and
  `review_required` (sensitive/contradicted events stay in the newsroom).

### Deferred (not Phase 5)

- **Live social / search APIs:** replace Phase 4 momentum and search-interest
  proxies with a real social firehose and Google Trends.
- **Editorial synthesis:** generate a neutral event brief/summary and headline
  candidates from clustered, *evidenced* coverage.
- **More adapters into the pipeline:** Website crawler, API, and (Phase 1.5)
  Telegram adapters so RSS-less and Telegram-first sources feed the same
  intelligence + verification flow.
- **Visual Director:** implement `ImageProvider` (Gemini/Imagen) for the
  Instagram image zone per the brand visual styles.
- **Backfill embeddings** if `EMBEDDING_DIM`/model changes (re-embed + reindex).

## Local development

See the root [`README.md`](../README.md) for setup, including the Supabase
pooler `DATABASE_URL` shape, migrations, and running the API + worker + beat +
dashboard via `docker-compose` or manually.
