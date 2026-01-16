"""FastAPI dependency injection for the GitLab Queue application.

Provides database sessions, authentication, and other injectable dependencies
for API endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gitlab_queue.auth.jwt_handler import (
    InvalidTokenError,
    TokenExpiredError,
    decode_token,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from gitlab_queue.config import Settings
    from gitlab_queue.db.database import Database

# Global database instance (initialized in app startup)
_database: Database | None = None

# Global settings instance (initialized in app startup)
_settings: Settings | None = None


def get_database() -> Database:
    """Get the global database instance.

    Returns:
        The initialized database instance.

    Raises:
        RuntimeError: If database is not initialized.
    """
    if _database is None:
        raise RuntimeError("Database not initialized. Call set_database() during app startup.")
    return _database


def set_database(db: Database) -> None:
    """Set the global database instance during app startup.

    Args:
        db: The initialized Database instance.
    """
    global _database
    _database = db


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        The initialized settings instance.

    Raises:
        RuntimeError: If settings are not initialized.
    """
    if _settings is None:
        raise RuntimeError("Settings not initialized. Call set_settings() during app startup.")
    return _settings


def set_settings(settings: Settings) -> None:
    """Set the global settings instance during app startup.

    Args:
        settings: The loaded Settings instance.
    """
    global _settings
    _settings = settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency to get a database session.

    This dependency provides a database session with automatic rollback
    on exceptions. Callers must explicitly commit to persist changes.

    Yields:
        AsyncSession: A database session for the request.

    Example:
        ```python
        from fastapi import Depends
        from gitlab_queue.dependencies import DbSession

        @app.get("/users")
        async def get_users(db: DbSession):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    db = get_database()
    async with db.session() as session:
        yield session


async def get_db_transaction() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for atomic database transactions.

    This dependency provides a database session that automatically
    commits on success or rolls back on failure. Use this for
    endpoints that modify data.

    Yields:
        AsyncSession: A database session within a transaction.

    Example:
        ```python
        from fastapi import Depends
        from gitlab_queue.dependencies import DbTransaction

        @app.post("/users")
        async def create_user(user: UserCreate, db: DbTransaction):
            db_user = User(**user.dict())
            db.add(db_user)
            # Automatic commit on success
            return db_user
        ```
    """
    db = get_database()
    async with db.transaction() as session:
        yield session


# Type aliases for cleaner dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
DbTransaction = Annotated[AsyncSession, Depends(get_db_transaction)]


# =============================================================================
# Authentication Dependencies
# =============================================================================


def _extract_bearer_token(authorization: str | None) -> str:
    """Extract bearer token from Authorization header.

    Args:
        authorization: Authorization header value.

    Returns:
        Token string.

    Raises:
        HTTPException: If header is missing or invalid.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parts[1]


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """FastAPI dependency to get the current authenticated user."""
    token = _extract_bearer_token(authorization)
    settings = get_settings()

    try:
        payload = decode_token(token, settings)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": payload.get("sub"),
        "username": payload.get("username"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "avatar_url": payload.get("avatar_url"),
    }


# Type alias for authenticated user dependency
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


__all__ = [
    "CurrentUser",
    "DbSession",
    "DbTransaction",
    "get_current_user",
    "get_database",
    "get_db_session",
    "get_db_transaction",
    "get_settings",
    "set_database",
    "set_settings",
]
