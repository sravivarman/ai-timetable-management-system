"""Password hashing and JWT utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password with Argon2."""
    return password_hash.hash(password)


def verify_password(password: str, password_hash_value: str) -> bool:
    """Verify a password against its Argon2 hash."""
    return password_hash.verify(password, password_hash_value)


def create_token(subject: UUID, token_type: str, token_version: int, expires_delta: timedelta) -> str:
    """Create a typed signed token tied to the user's token version."""
    expires_at = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "ver": token_version,
        "jti": str(uuid4()),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: UUID, token_version: int) -> str:
    """Create a short-lived access token."""
    return create_token(
        subject,
        "access",
        token_version,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: UUID, token_version: int) -> str:
    """Create a long-lived refresh token."""
    return create_token(
        subject,
        "refresh",
        token_version,
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode a token and enforce its intended use."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
