"""Async SQLite database setup with SQLAlchemy.

Provides async database engine, session factory, and lifecycle management for
the GitLab Merge Queue Bot. Uses SQLite in WAL mode for concurrent reads.

Example:
    >>> from gitlab_queue.db.database import Database
    >>> from gitlab_queue.config import load_settings
    >>> settings = load_settings()
    >>> async with Database(settings.database_url) as db:
    ...     async with db.session() as session:
    ...         # Use session for queries
    ...         pass
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gitlab_queue.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

log = get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class DatabaseError(Exception):
    """Base exception for database operations."""


class DatabaseAlreadyInitializedError(DatabaseError):
    """Raised when attempting to initialize an already initialized database."""


class DatabaseNotInitializedError(DatabaseError):
    """Raised when accessing database before initialization."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when database configuration is invalid."""


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DatabaseStatus:
    """Health check status for the database connection."""

    connected: bool
    wal_mode_enabled: bool
    foreign_keys_enabled: bool
    database_path: str
    error: str | None = None


@dataclass
class Database:
    """Async SQLite database manager with WAL mode support.

    Provides async engine, session factory, health checks, and graceful shutdown.
    Designed to be used as an async context manager for proper lifecycle management.

    Attributes:
        database_url: SQLAlchemy database URL (e.g., "sqlite+aiosqlite:///data/queue.db").
        echo: Whether to log SQL queries (useful for debugging).
        allowed_base_path: Optional base directory for path validation. If set,
            database paths must be within this directory.

    Example:
        >>> db = Database("sqlite+aiosqlite:///data/queue.db")
        >>> await db.initialize()
        >>> async with db.session() as session:
        ...     result = await session.execute(text("SELECT 1"))
        ...     await session.commit()  # Explicit commit required
        >>> await db.close()

        # Or as context manager:
        >>> async with Database("sqlite+aiosqlite:///data/queue.db") as db:
        ...     async with db.session() as session:
        ...         result = await session.execute(text("SELECT 1"))
        ...         await session.commit()

        # For atomic operations, use transaction():
        >>> async with db.transaction() as session:
        ...     # Automatic commit on success, rollback on exception
        ...     await session.execute(...)
    """

    database_url: str
    echo: bool = False
    allowed_base_path: str | None = None
    _engine: AsyncEngine | None = field(default=None, init=False, repr=False)
    _session_factory: async_sessionmaker[AsyncSession] | None = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)
    _init_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def _build_engine_kwargs(self, is_memory_db: bool) -> dict[str, Any]:
        """Build engine keyword arguments based on database type."""
        kwargs: dict[str, Any] = {
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30.0,
            },
            "echo": self.echo,
        }

        if not is_memory_db:
            kwargs.update(
                {
                    "pool_size": 1,
                    "max_overflow": 20,
                    "pool_timeout": 30,
                    "pool_recycle": 3600,
                    "pool_pre_ping": True,
                }
            )

        return kwargs

    async def _configure_sqlite_pragmas(self, conn: Any, is_memory_db: bool) -> str:
        """Configure SQLite pragmas and return journal mode."""
        if not is_memory_db:
            result = await conn.execute(text("PRAGMA journal_mode=WAL"))
            actual_mode = result.scalar()
            if actual_mode != "wal":
                raise DatabaseConnectionError(
                    f"Failed to enable WAL mode. Got '{actual_mode}' instead. "
                    "Check filesystem compatibility (network drives don't support WAL)."
                )
        else:
            actual_mode = "memory"

        await conn.execute(text("PRAGMA synchronous=FULL"))
        await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))

        result = await conn.execute(text("PRAGMA foreign_keys"))
        if not result.scalar():
            raise DatabaseConnectionError("Failed to enable foreign key constraints")

        return str(actual_mode)

    async def initialize(self) -> None:
        """Initialize the database engine and enable WAL mode."""
        async with self._init_lock:
            if self._initialized:
                raise DatabaseAlreadyInitializedError("Database is already initialized")

            log.info("Initializing database", database_url=self._masked_url)
            self._ensure_data_directory()

            is_memory_db = ":memory:" in self.database_url
            engine_kwargs = self._build_engine_kwargs(is_memory_db)
            self._engine = create_async_engine(self.database_url, **engine_kwargs)

            async with self._engine.begin() as conn:
                actual_mode = await self._configure_sqlite_pragmas(conn, is_memory_db)
                log.debug(
                    "Database configuration verified",
                    journal_mode=actual_mode,
                    synchronous="FULL",
                    foreign_keys=True,
                )

            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            self._initialized = True
            log.info("Database initialized successfully")

    def _ensure_data_directory(self) -> None:
        """Ensure the data directory exists for SQLite database file.

        Validates the path is within the allowed base directory if configured,
        to prevent path traversal attacks.

        Raises:
            DatabaseConfigurationError: If path is outside allowed directory.
        """
        if ":///" not in self.database_url:
            return

        # Extract path from SQLite URL (e.g., "sqlite+aiosqlite:///data/queue.db")
        path_part = self.database_url.split(":///", 1)[1]

        # Resolve to absolute path for security validation
        db_path = Path(path_part).resolve()

        # Validate path is within allowed directory if configured
        if self.allowed_base_path is not None:
            allowed_base = Path(self.allowed_base_path).resolve()
            try:
                db_path.relative_to(allowed_base)
            except ValueError:
                raise DatabaseConfigurationError(
                    f"Database path '{db_path}' is outside allowed directory '{allowed_base}'. "
                    "This could indicate a path traversal attack."
                ) from None

        # Create parent directory if it doesn't exist
        parent_dir = db_path.parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
            log.debug("Created data directory", path=str(parent_dir))

    @property
    def _masked_url(self) -> str:
        """Return database URL with credentials masked for logging."""
        if "@" in self.database_url:
            # Mask password in connection string
            parts = self.database_url.split("@")
            if ":" in parts[0]:
                prefix = parts[0].rsplit(":", 1)[0]
                return f"{prefix}:***@{parts[1]}"
        return self.database_url

    @property
    def engine(self) -> AsyncEngine:
        """Return the SQLAlchemy async engine.

        Raises:
            DatabaseNotInitializedError: If database is not initialized.
        """
        if self._engine is None:
            raise DatabaseNotInitializedError("Database not initialized. Call initialize() first.")
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Create a new async database session.

        This session does NOT auto-commit. You must explicitly call
        `await session.commit()` before exiting the context to persist changes.
        On exception, the session is automatically rolled back.

        For automatic commit/rollback semantics, use `transaction()` instead.

        Yields:
            AsyncSession: An async SQLAlchemy session.

        Raises:
            DatabaseNotInitializedError: If database is not initialized.

        Example:
            >>> async with db.session() as session:
            ...     session.add(user)
            ...     await session.commit()  # Required to persist changes
        """
        if self._session_factory is None:
            raise DatabaseNotInitializedError("Database not initialized. Call initialize() first.")

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                log.debug("Session rolled back due to exception")
                raise
            finally:
                # Warn about uncommitted transactions
                if session.in_transaction():
                    await session.rollback()
                    log.warning("Rolled back uncommitted transaction at session exit. Caller should explicitly commit.")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Create a new session with automatic commit/rollback.

        Use this for atomic operations that should commit on success
        or rollback on failure. This provides cleaner transaction semantics
        for multi-step operations.

        Yields:
            AsyncSession: An async SQLAlchemy session within a transaction.

        Raises:
            DatabaseNotInitializedError: If database is not initialized.

        Example:
            >>> async with db.transaction() as session:
            ...     # Multiple operations within atomic transaction
            ...     session.add(user)
            ...     session.add(audit_log)
            ...     # Automatic commit on success, rollback on exception
        """
        if self._session_factory is None:
            raise DatabaseNotInitializedError("Database not initialized. Call initialize() first.")

        async with self._session_factory() as session:
            try:
                async with session.begin():
                    yield session
                    # Commits automatically on __aexit__ if no exception
            except Exception:
                # Already rolled back by session.begin() context manager
                log.debug("Transaction rolled back due to exception")
                raise

    async def health_check(self) -> DatabaseStatus:
        """Check database connection health.

        Performs a lightweight query to verify the database is accessible,
        WAL mode is enabled, and foreign keys are enforced.

        Returns:
            DatabaseStatus: Current health status of the database.
            Note: database_path is masked to hide credentials.
        """
        if not self._initialized or self._engine is None:
            return DatabaseStatus(
                connected=False,
                wal_mode_enabled=False,
                foreign_keys_enabled=False,
                database_path=self._masked_url,
                error="Database not initialized",
            )

        try:
            async with self._engine.begin() as conn:
                # Check connection
                await conn.execute(text("SELECT 1"))

                # Check WAL mode
                result = await conn.execute(text("PRAGMA journal_mode"))
                journal_mode = result.scalar()
                wal_enabled = journal_mode == "wal"

                # Check foreign keys
                result = await conn.execute(text("PRAGMA foreign_keys"))
                fk_enabled = bool(result.scalar())

                return DatabaseStatus(
                    connected=True,
                    wal_mode_enabled=wal_enabled,
                    foreign_keys_enabled=fk_enabled,
                    database_path=self._masked_url,
                )
        except Exception as e:
            log.warning("Database health check failed", error=str(e))
            return DatabaseStatus(
                connected=False,
                wal_mode_enabled=False,
                foreign_keys_enabled=False,
                database_path=self._masked_url,
                error=str(e),
            )

    async def close(self) -> None:
        """Close the database connection gracefully.

        Disposes of the engine and cleans up resources. Safe to call
        multiple times.
        """
        if self._engine is not None:
            log.info("Closing database connection")
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            log.debug("Database connection closed")

    async def __aenter__(self) -> Database:
        """Async context manager entry - initializes database."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit - closes database connection."""
        await self.close()


async def create_database(
    database_url: str,
    echo: bool = False,
    allowed_base_path: str | None = None,
) -> Database:
    """Create and initialize a database instance.

    Convenience function for creating a database without using context manager.
    The caller is responsible for calling close() when done.

    Args:
        database_url: SQLAlchemy database URL.
        echo: Whether to log SQL queries.
        allowed_base_path: Optional base directory for path validation.

    Returns:
        Initialized Database instance.

    Example:
        >>> db = await create_database("sqlite+aiosqlite:///data/queue.db")
        >>> try:
        ...     async with db.session() as session:
        ...         # Use session
        ...         await session.commit()
        >>> finally:
        ...     await db.close()
    """
    db = Database(
        database_url=database_url,
        echo=echo,
        allowed_base_path=allowed_base_path,
    )
    await db.initialize()
    return db


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
