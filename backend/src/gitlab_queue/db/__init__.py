"""Database module for GitLab Merge Queue Bot.

Provides async SQLite database access with SQLAlchemy, including:
- Async engine with WAL mode for concurrent reads
- Session factory for database operations
- Transaction helper for atomic operations
- Health check endpoints
- Graceful shutdown handling
- Custom exception hierarchy

Example:
    >>> from gitlab_queue.db import Database
    >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
    ...     async with db.session() as session:
    ...         # Perform database operations
    ...         await session.commit()

    # For atomic operations:
    >>> async with db.transaction() as session:
    ...     # Automatic commit on success, rollback on exception
    ...     session.add(user)
"""

from gitlab_queue.db.database import (
    Database,
    DatabaseAlreadyInitializedError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseNotInitializedError,
    DatabaseStatus,
    create_database,
)

__all__: list[str] = [
    "Database",
    "DatabaseAlreadyInitializedError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseNotInitializedError",
    "DatabaseStatus",
    "create_database",
]
