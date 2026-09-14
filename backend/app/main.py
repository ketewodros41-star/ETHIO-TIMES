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


async def _periodic_telegram_runner() -> None:
    """Periodically plan and publish due Telegram posts automatically when enabled."""
    await asyncio.sleep(15)  # Wait 15s after server startup
    while True:
        try:
            from app.db.session import SessionLocal
            from app.models.telegram_post import TelegramPublishingSettings
            from app.workers.tasks import plan_telegram_posts, publish_due_telegram_posts

            # Self-healing safety guard: if enabled=True but dry_run=True, auto-reset dry_run to False
            check_session = SessionLocal()
            try:
                policy = check_session.get(TelegramPublishingSettings, 1)
                if policy and policy.enabled and policy.dry_run:
                    logger.critical(
                        "dry_run_anomaly_detected_resetting",
                        detail="Telegram publishing is enabled but dry_run was True. Auto-resetting dry_run to False.",
                    )
                    policy.dry_run = False
                    check_session.commit()
            except Exception as e:
                check_session.rollback()
                logger.warning("dry_run_self_healing_error", error=str(e))
            finally:
                check_session.close()

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, plan_telegram_posts)
            await loop.run_in_executor(None, publish_due_telegram_posts)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("periodic_telegram_runner_error", error=str(exc))

        await asyncio.sleep(60)



@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    logger.info("startup", service=settings.project_name, environment=settings.environment)
    poller_task = asyncio.create_task(_periodic_feed_poller())
    telegram_task = asyncio.create_task(_periodic_telegram_runner())
    yield
    poller_task.cancel()
    telegram_task.cancel()
    try:
        await asyncio.gather(poller_task, telegram_task, return_exceptions=True)
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


from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_server_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {type(exc).__name__}: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.project_name,
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/api/v1",
    }
