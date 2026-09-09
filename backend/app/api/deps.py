"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, get_subject_from_token
from app.db.session import get_session

# auto_error=False so most endpoints remain open in Phase 1 while the auth
# system is still scaffolding; protected endpoints use `require_auth`.
_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    yield from get_session()


def get_current_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    if credentials is None:
        return None
    try:
        return get_subject_from_token(credentials.credentials)
    except TokenError:
        return None


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return get_subject_from_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
