"""Authentication & password hashing utilities (Phase 1 scaffolding).

This provides JWT issue/verify and password hashing helpers. A real user
store and login flow will be wired in a later phase; for now the auth layer
exposes a demo login and a dependency that decodes bearer tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str, extra_claims: dict[str, Any] | None = None
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


class TokenError(Exception):
    """Raised when a token cannot be validated."""


def get_subject_from_token(token: str) -> str:
    try:
        payload = decode_access_token(token)
    except JWTError as exc:  # pragma: no cover - thin wrapper
        raise TokenError(str(exc)) from exc
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token missing subject")
    return subject
