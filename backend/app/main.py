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


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    logger.info("startup", service=settings.project_name, environment=settings.environment)
    yield
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
