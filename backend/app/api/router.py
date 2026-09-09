"""Aggregate API router (v1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    articles,
    auth,
    events,
    health,
    ingest,
    pipeline,
    sources,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sources.router)
api_router.include_router(articles.router)
api_router.include_router(events.router)
api_router.include_router(pipeline.router)
api_router.include_router(ingest.router)
