"""Shared schema primitives."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    total: int = Field(..., description="Total number of matching records")
    limit: int
    offset: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class Message(BaseModel):
    detail: str
