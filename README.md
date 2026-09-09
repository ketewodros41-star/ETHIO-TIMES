# ETHIOTIMES

**Ethiopian News Intelligence & Automated Social Media Publishing Platform.**

ETHIOTIMES is a **News Intelligence Engine first**: it monitors a curated
registry of Ethiopian and international sources, ingests and normalizes their
content, and (in later phases) clusters, verifies, analyzes, and publishes
premium editorial posts to Instagram — and later Telegram, X, Facebook, TikTok,
and a website.

This repository contains the **Phase 1 foundation**: real database schema and
migrations, a seeded Ethiopian source registry, a working RSS ingestion pipeline
on Celery, the FastAPI backend, and a dark "newsroom terminal" Next.js dashboard.

> Phases 2–8 (event clustering, verification, Gemini analysis/embeddings, the
> Visual Director, Instagram publishing, carousels, multi-channel distribution)
> are **out of scope** for Phase 1 and exist only as stubs/TODOs. See
> [`docs/architecture.md`](docs/architecture.md).

---

## Architecture at a glance

```
Next.js dashboard  ──REST──▶  FastAPI  ──enqueue──▶  Celery (Redis)  ──▶  Source adapters (RSS ✓)
      (dark newsroom)            │                        │                        │
                                 └──────── SQLAlchemy ─────┴── PostgreSQL + pgvector (Supabase)
```

- **Frontend:** Next.js (App Router) · TypeScript · Tailwind · shadcn-style UI · TanStack Query
- **Backend:** FastAPI · Pydantic · SQLAlchemy · Alembic
- **DB:** PostgreSQL + `pgvector` (Supabase-compatible)
- **Background:** Celery + Redis (beat schedule + per-source ingest tasks)
- **AI:** provider abstractions only in Phase 1 (`AIProvider`, `ImageProvider` + Gemini stubs)

Full design docs:
- [`docs/architecture.md`](docs/architecture.md) — system + data model + roadmap + Telegram warning
- [`docs/brand-guidelines.md`](docs/brand-guidelines.md) — ETHIOTIMES brand DNA
- [`docs/design-tokens.json`](docs/design-tokens.json) — canonical tokens
- [`docs/instagram-templates.md`](docs/instagram-templates.md) — post template stubs

---

## Repository layout

```
ethiotimes/
├── backend/          # FastAPI app, models, migrations, Celery workers, ingestion
│   └── app/{api,core,db,models,schemas,services,repositories,pipelines,workers,integrations,data}
├── frontend/         # Next.js dashboard + Instagram post templates
├── docs/             # architecture, brand guidelines, design tokens
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick start

### Option A — Docker Compose (everything)

```bash
cp .env.example .env          # then edit as needed (no secrets committed)
docker compose up --build
```

This starts Postgres (pgvector), Redis, the API (runs migrations on boot),
a Celery worker, Celery beat, and the dashboard.

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

### Option B — Run against Supabase + local services

#### 1. Configure the database URL (Supabase pooler)

Set `DATABASE_URL` in `.env` to your Supabase **pooler** connection string:

```
postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Some Supabase pooler modes don't support the DDL/locks migrations need. If you
hit issues running migrations, set a **direct** connection for migrations only:

```
DATABASE_MIGRATION_URL=postgresql+psycopg://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres
```

Enable pgvector once in the Supabase SQL editor (migration `0001` also runs
`CREATE EXTENSION IF NOT EXISTS vector`):

```sql
create extension if not exists vector;
```

#### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Apply schema + seed the Ethiopian source registry
alembic upgrade head

# Run the API
uvicorn app.main:app --reload --port 8000
```

#### 3. Redis + Celery (ingestion)

```bash
# Redis (or use docker: docker run -p 6379:6379 redis:7-alpine)
redis-server

# In separate terminals (from backend/, venv active):
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO -Q ingestion
celery -A app.workers.celery_app.celery_app beat  --loglevel=INFO
```

#### 4. Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
# http://localhost:3000
```

---

## Trigger an ingest (RSS → articles via Celery)

Ingestion is **always enqueued** — never run in the API request path. Beat polls
due sources every 5 minutes automatically; to trigger manually:

```bash
# Enqueue all active sources
curl -X POST http://localhost:8000/api/v1/ingest/trigger \
  -H 'Content-Type: application/json' -d '{}'

# Enqueue a single source
curl -X POST http://localhost:8000/api/v1/ingest/trigger \
  -H 'Content-Type: application/json' -d '{"source_id":"<uuid>"}'
```

The Celery worker fetches each RSS feed, normalizes items, deduplicates by
`canonical_url`, stores new `articles`, updates source health, and records a
`pipeline_jobs` row. Each new article is then enqueued into the **intelligence
pipeline** (below). The dashboard's **Sources** and **Articles** pages reflect
the results.

---

## Phase 2 — Intelligence pipeline

After ingestion, each article flows through:

```
relevance → analysis → embedding → clustering (→ event)
```

powered by Gemini (with deterministic fallbacks). See
[docs/architecture.md](docs/architecture.md#intelligence-pipeline-phase-2) for
the full design, model choices, and cost notes.

### Enable Gemini (local runtime only)

Set your key in `.env` (never commit it):

```
GEMINI_API_KEY=your-key-here
```

Without a key, relevance + analysis still run via deterministic fallbacks, but
embeddings and event clustering (which require the model) are skipped.

The same Celery worker/beat you already run handles the pipeline — no extra
process is needed:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO -Q ingestion
celery -A app.workers.celery_app.celery_app beat  --loglevel=INFO
```

Beat enqueues `poll_pending_articles` every 2 minutes; `ingest_source` also
enqueues `process_article` for each new article immediately. Watch progress:

```bash
curl -s http://localhost:8000/api/v1/pipeline/stats | jq
```

Clustered stories appear on the dashboard **Events** feed and **Event detail**
pages (grouped coverage, sources, relations, timeline, cluster confidence).

---

## Seeded sources

Migration `0002` seeds ~20 Ethiopian-focused sources: Addis Standard, Capital
Ethiopia, The Reporter Ethiopia, Addis Fortune, Borkena, Ethiopia Insight, ENA,
Fana (FBC), Tikvah Ethiopia (Telegram, flagged `needs_verification`), officials
(PMO, MFA, MoF, NBE, EIC, ESS), and international media/wires (BBC Africa, Al
Jazeera, DW, Reuters, AP).

Real RSS feeds are used where confirmed; sources without a confirmed feed are
seeded with `rss_url = NULL` for the website/API adapters in later phases.

> ⚠️ **Telegram impersonation warning.** Telegram handles are **not** fabricated.
> Telegram-first sources are seeded with `verification_status = needs_verification`,
> no `@handle`, and `is_active = false` until confirmed against the outlet's
> official website. See [`docs/architecture.md`](docs/architecture.md).

---

## API surface (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | Service + DB health |
| GET | `/api/v1/source-health` | Per-source health |
| POST | `/api/v1/auth/login` | Token issue (scaffolding; demo login in `local`) |
| GET | `/api/v1/auth/me` | Current subject |
| GET/POST | `/api/v1/sources` | List / create sources |
| GET/PATCH/DELETE | `/api/v1/sources/{id}` | Read / update / delete |
| GET | `/api/v1/articles` | List articles (filter, paginate) |
| GET | `/api/v1/articles/{id}` | Article detail (incl. analysis + processing state) |
| GET | `/api/v1/events` | List clustered events (filter, paginate) |
| GET | `/api/v1/events/{id}` | Event detail (grouped articles, timeline) |
| GET | `/api/v1/pipeline/stats` | Pipeline processing stats |
| POST | `/api/v1/ingest/trigger` | **Enqueue** ingestion |

Interactive docs at `/docs`.

---

## Tests & linting

Backend tests use an isolated `ethiotimes_test` database (override with
`TEST_DATABASE_URL`); DB-backed tests skip automatically if it is unreachable.
Integration tests mock Gemini — **no production AI calls run in CI**.

```bash
cd backend
createdb ethiotimes_test    # one-time (or let CI provision it)
export TEST_DATABASE_URL=postgresql+psycopg://ethiotimes:ethiotimes@localhost:5432/ethiotimes_test
pytest                       # unit + integration (relevance, clustering, pipeline, ...)
ruff check app migrations tests   # lint

cd ../frontend
npm run typecheck            # tsc --noEmit
npm run build                # production build
```

---

## Security

- No secrets are committed. All config comes from environment (`.env.example`).
- The dashboard **never displays secret values** (see Settings page).
- Provider (Gemini) calls are stubbed in Phase 1 so no paid API is invoked.
