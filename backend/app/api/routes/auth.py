"""Auth routes (Phase 1 scaffolding).

Provides a minimal token endpoint. A full user store, registration, refresh
tokens, and role-based access control are a later phase. In `local` environment
a demo login is allowed so the dashboard can exercise protected flows; outside
`local` the endpoint requires a real user row.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_auth
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> Token:
    user = session.scalar(select(User).where(User.email == payload.email))

    if user is None:
        # Local convenience: allow a demo operator so the dashboard is usable
        # before a real user store exists. Never enabled outside local.
        if settings.environment == "local" and payload.password == "demo":
            token = create_access_token(subject=payload.email, extra_claims={"demo": True})
            return Token(access_token=token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserRead | dict)
def me(
    subject: str = Depends(require_auth), session: Session = Depends(get_db)
) -> UserRead | dict:
    user = session.scalar(select(User).where(User.email == subject)) or (
        session.get(User, subject) if _looks_like_uuid(subject) else None
    )
    if user is None:
        # Demo token path
        return {"subject": subject, "demo": True}
    return UserRead.model_validate(user)


def _looks_like_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
