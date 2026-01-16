"""JWT token handling for dashboard authentication.

This module provides utilities for creating and validating JWT tokens
used for authenticating users on the dashboard after GitLab OAuth login.

Example:
    >>> from gitlab_queue.config import load_settings
    >>> from gitlab_queue.auth.jwt_handler import create_access_token, decode_token
    >>> settings = load_settings()
    >>> user_data = {"id": 123, "username": "johndoe", "email": "john@example.com"}
    >>> token = create_access_token(user_data, settings)
    >>> decoded = decode_token(token, settings)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import jwt

if TYPE_CHECKING:
    from gitlab_queue.config import Settings


class JWTError(Exception):
    """Base exception for JWT-related errors."""


class TokenExpiredError(JWTError):
    """Raised when the JWT token has expired."""


class InvalidTokenError(JWTError):
    """Raised when the JWT token is invalid or malformed."""


def create_access_token(
    user_data: dict[str, Any],
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token for an authenticated user.

    The token includes user information from GitLab OAuth and
    standard JWT claims (exp, iat, sub).

    Args:
        user_data: User information from GitLab API. Expected keys:
            - id: GitLab user ID (required)
            - username: GitLab username (required)
            - name: Display name
            - email: User email
            - avatar_url: URL to user avatar
            - project_id: GitLab project ID user has access to
        settings: Application settings containing jwt_secret and jwt_expiration_hours.
        expires_delta: Optional custom expiration time. If not provided,
            uses settings.jwt_expiration_hours.

    Returns:
        Encoded JWT token string.

    Example:
        >>> user = {"id": 123, "username": "johndoe", "name": "John Doe"}
        >>> token = create_access_token(user, settings)
    """
    now = datetime.now(UTC)

    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_expiration_hours)

    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_data["id"]),
        "username": user_data["username"],
        "name": user_data.get("name", user_data["username"]),
        "email": user_data.get("email"),
        "avatar_url": user_data.get("avatar_url"),
        "project_id": user_data.get("project_id"),
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(
    token: str,
    settings: Settings,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Validates the token signature and expiration time.

    Args:
        token: The JWT token string to decode.
        settings: Application settings containing jwt_secret.

    Returns:
        Decoded token payload as a dictionary.

    Raises:
        TokenExpiredError: If the token has expired.
        InvalidTokenError: If the token is invalid, malformed,
            or has an invalid signature.

    Example:
        >>> try:
        ...     payload = decode_token(token, settings)
        ...     print(f"User: {payload['username']}")
        ... except TokenExpiredError:
        ...     print("Token expired, please login again")
        ... except InvalidTokenError:
        ...     print("Invalid token")
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
        )
        return cast("dict[str, Any]", payload)
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {e}") from e


def get_token_expiration(settings: Settings) -> datetime:
    """Get the expiration time for a new token.

    Useful for setting cookie expiration or informing the client
    when the token will expire.

    Args:
        settings: Application settings containing jwt_expiration_hours.

    Returns:
        Datetime when a newly created token would expire.
    """
    return datetime.now(UTC) + timedelta(hours=settings.jwt_expiration_hours)


__all__: list[str] = [
    "InvalidTokenError",
    "JWTError",
    "TokenExpiredError",
    "create_access_token",
    "decode_token",
    "get_token_expiration",
]
