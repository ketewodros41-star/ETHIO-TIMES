"""Pytest fixtures.

Database-backed tests use an isolated ``ethiotimes_test`` database (override with
``TEST_DATABASE_URL``). Each test runs inside a transaction that is rolled back,
so tests are fully isolated and never touch the dev database. If the test DB is
unreachable, DB-backed tests are skipped rather than failing the whole suite.
"""

from __future__ import annotations

import os

import pytest
from app.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ethiotimes:ethiotimes@localhost:5432/ethiotimes_test",
)


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - DB not available -> skip DB tests
        pytest.skip(f"Test database unavailable: {exc}", allow_module_level=False)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:  # noqa: ANN001
    connection = db_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
