"""ETHIOTIMES FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


import asyncio


async def _periodic_feed_poller() -> None:
    """Automatically poll active news sources (Tikvah, RSS, etc.) and cluster into events.
    Runs every 90 seconds so real-time news detection works in all environments.
    """
    await asyncio.sleep(10)  # Wait 10s after server startup
    while True:
        try:
            from app.api.routes.ingest import _background_run_ingest
            from app.db.session import SessionLocal
            from app.repositories.source_repository import SourceRepository

            session = SessionLocal()
            try:
                active_ids = SourceRepository(session).list_active_ids()
            finally:
                session.close()

            if active_ids:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _background_run_ingest, active_ids)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("periodic_feed_poller_error", error=str(exc))

        await asyncio.sleep(90)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    logger.info("startup", service=settings.project_name, environment=settings.environment)
    poller_task = asyncio.create_task(_periodic_feed_poller())
    yield
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    logger.info("shutdown", service=settings.project_name)


app = FastAPI(
    title="ETHIOTIMES API",
    version="0.1.0",
    description=(
        "Ethiopian News Intelligence Engine — Phase 1 foundation. "
        "Source registry, RSS ingestion, and dashboard APIs."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.project_name,
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/api/v1",
    }
