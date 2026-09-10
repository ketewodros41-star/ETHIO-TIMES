"""SQLAlchemy engine & session management.

Uses a synchronous engine with psycopg3. This works transparently against a
local Postgres or a Supabase pooler connection string (the pooler is designed
for short-lived connections, so we keep pool sizes modest and enable
pre-ping to recover from dropped connections).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    pool_timeout=20,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
