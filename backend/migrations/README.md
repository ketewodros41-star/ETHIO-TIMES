# Database migrations (Alembic)

- `alembic upgrade head` — apply all migrations.
- `alembic revision --autogenerate -m "message"` — generate a new migration from model changes.
- `alembic downgrade -1` — roll back one migration.

The connection URL is read from application settings (`DATABASE_MIGRATION_URL`
if set, otherwise `DATABASE_URL`). See `../app/core/config.py`.

Migration `0001` enables the `vector` (pgvector) and `pgcrypto` extensions and
creates all Phase 1 tables. Migration `0002` seeds the Ethiopian source registry.
