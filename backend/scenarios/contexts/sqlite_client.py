"""SQLite test context for Vedro scenarios.

Provides in-memory SQLite database for isolated test execution.
Uses the existing Database class from gitlab_queue.db.database.

Example:
    >>> from scenarios.contexts.sqlite_client import test_database
    >>>
    >>> @scenario()
    >>> async def test_queue_operations():
    ...     with given:
    ...         db = await test_database()
    ...     with when:
    ...         # perform database operations
    ...     with then:
    ...         # assert results
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from gitlab_queue.db.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def test_database() -> AsyncIterator[Database]:
    """Provide an in-memory SQLite database for testing.

    Creates a fresh in-memory database for each test, ensuring isolation.
    The database is automatically cleaned up after the test completes.

    Yields:
        Database: Initialized in-memory database instance.

    Example:
        >>> async with test_database() as db:
        ...     async with db.session() as session:
        ...         # Use session for queries
        ...         await session.commit()
    """
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


@asynccontextmanager
async def test_session(db: Database) -> AsyncIterator[AsyncSession]:
    """Provide a test session with automatic rollback.

    Creates a session that automatically rolls back all changes,
    ensuring test isolation without manual cleanup.

    Args:
        db: Initialized Database instance.

    Yields:
        AsyncSession: Database session for the test.

    Example:
        >>> async with test_database() as db:
        ...     async with test_session(db) as session:
        ...         # All changes are rolled back after the test
    """
    async with db.session() as session:
        yield session
        # Explicit rollback to ensure no data persists between tests
        await session.rollback()


@asynccontextmanager
async def test_transaction(db: Database) -> AsyncIterator[AsyncSession]:
    """Provide a test transaction that commits on success.

    Use this when you need to test transaction behavior
    with actual commits.

    Args:
        db: Initialized Database instance.

    Yields:
        AsyncSession: Database session within a transaction.

    Example:
        >>> async with test_database() as db:
        ...     async with test_transaction(db) as session:
        ...         # Changes are committed on success
    """
    async with db.transaction() as session:
        yield session


__all__ = [
    "test_database",
    "test_session",
    "test_transaction",
]
