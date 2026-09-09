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

## Roadmap (phases)

| Phase | Scope |
|-------|-------|
| **1 (this)** | Foundation: schema+migrations, source registry, RSS ingestion, Celery scaffolding, dashboard, brand system, provider abstractions. |
| 1.5 | Verified Telegram channel ingestion. |
| 2 | Website/API adapters; Gemini relevance filter; embeddings; event clustering (news_events). |
| 3 | Verification & trust scoring; editorial analysis; Visual Director (image generation). |
| 4 | Instagram post composition (Playwright render) + publishing. |
| 5–8 | Carousels; Telegram/X/Facebook/TikTok/website distribution; full editorial AI; analytics. |

## Local development

See the root [`README.md`](../README.md) for setup, including the Supabase
pooler `DATABASE_URL` shape, migrations, and running the API + worker + beat +
dashboard via `docker-compose` or manually.
