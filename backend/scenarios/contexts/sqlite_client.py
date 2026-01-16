"""SQLite test context for Vedro scenarios.

Provides in-memory SQLite database for isolated test execution.
Uses the existing Database class from gitlab_queue.db.database.

Example:
    >>> from scenarios.contexts.sqlite_client import initialized_test_database
    >>>
    >>> class Scenario(vedro.Scenario):
    ...     subject = "perform database operations"
    ...
    ...     async def given_database(self):
    ...         self._db_ctx = initialized_test_database()
    ...         self.db = await self._db_ctx.__aenter__()
    ...
    ...     async def when_query_executed(self):
    ...         # perform database operations
    ...
    ...     async def then_result_is_correct(self):
    ...         # assert results
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import vedro

from gitlab_queue.db.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


@vedro.context
@asynccontextmanager
async def initialized_test_database() -> AsyncIterator[Database]:
    """Provide an initialized in-memory SQLite database for testing.

    Creates a fresh in-memory database for each test, ensuring isolation.
    The database is automatically cleaned up after the test completes.
    Includes guaranteeing assertion that database is connected.

    Yields:
        Database: Initialized in-memory database instance.

    Example:
        >>> async with initialized_test_database() as db:
        ...     async with db.session() as session:
        ...         # Use session for queries
        ...         await session.commit()
    """
    db = Database(database_url="sqlite+aiosqlite:///:memory:")
    await db.initialize()
    health = await db.health_check()
    assert health.connected, "Database should be connected after initialization"
    try:
        yield db
    finally:
        await db.close()


# Alias for backward compatibility
test_database = initialized_test_database


@vedro.context
@asynccontextmanager
async def opened_test_session(db: Database) -> AsyncIterator[AsyncSession]:
    """Provide an opened test session with automatic rollback.

    Creates a session that automatically rolls back all changes,
    ensuring test isolation without manual cleanup.

    Args:
        db: Initialized Database instance.

    Yields:
        AsyncSession: Database session for the test.

    Example:
        >>> async with initialized_test_database() as db:
        ...     async with opened_test_session(db) as session:
        ...         # All changes are rolled back after the test
    """
    async with db.session() as session:
        yield session
        # Explicit rollback to ensure no data persists between tests
        await session.rollback()


# Alias for backward compatibility
test_session = opened_test_session


@vedro.context
@asynccontextmanager
async def started_test_transaction(db: Database) -> AsyncIterator[AsyncSession]:
    """Provide a started test transaction that commits on success.

    Use this when you need to test transaction behavior
    with actual commits.

    Args:
        db: Initialized Database instance.

    Yields:
        AsyncSession: Database session within a transaction.

    Example:
        >>> async with initialized_test_database() as db:
        ...     async with started_test_transaction(db) as session:
        ...         # Changes are committed on success
    """
    async with db.transaction() as session:
        yield session


# Alias for backward compatibility
test_transaction = started_test_transaction


__all__ = [
    # New names (preferred)
    "initialized_test_database",
    "opened_test_session",
    "started_test_transaction",
    # Aliases for backward compatibility
    "test_database",
    "test_session",
    "test_transaction",
]
