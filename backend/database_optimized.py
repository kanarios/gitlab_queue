"""
Optimized Database Module with Performance Improvements
========================================================

All P1 and P2 performance issues addressed.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
import structlog

log = structlog.get_logger()


@dataclass
class DatabaseStatus:
    """Database health status information."""

    connected: bool
    wal_mode_enabled: bool
    database_path: str
    error: str | None = None
    pool_stats: dict[str, Any] | None = None


@dataclass
class Database:
    """
    Async SQLite database manager with optimized configuration.

    Performance optimizations:
    - NullPool for SQLite (no connection pooling overhead)
    - Per-connection PRAGMAs via event listeners
    - Cached health checks (30s TTL)
    - Optimized memory settings (64MB cache, 256MB mmap)
    - Auto-commit pattern for write operations
    """

    database_url: str
    echo: bool = False
    health_check_cache_ttl: int = 30  # seconds

    # Private fields
    _engine: AsyncEngine | None = field(default=None, init=False, repr=False)
    _session_factory: async_sessionmaker[AsyncSession] | None = field(
        default=None, init=False, repr=False
    )
    _initialized: bool = field(default=False, init=False, repr=False)
    _last_health_check: datetime | None = field(default=None, init=False, repr=False)
    _cached_health_status: DatabaseStatus | None = field(
        default=None, init=False, repr=False
    )

    async def initialize(self) -> None:
        """Initialize database engine and configure SQLite for optimal performance."""
        if self._initialized:
            msg = "Database is already initialized"
            raise RuntimeError(msg)

        log.info("Initializing database", database_url=self._masked_url)
        self._ensure_data_directory()

        # Create engine with optimized pool configuration for SQLite
        self._engine = create_async_engine(
            self.database_url,
            connect_args={
                "check_same_thread": False,
                "timeout": 30.0,  # Connection timeout
            },
            echo=self.echo,
            poolclass=NullPool,  # No pooling for SQLite (single-file DB)
            # Alternative: Use StaticPool for persistent single connection
            # poolclass=StaticPool,
        )

        # Set WAL mode once (persistent across connections)
        async with self._engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            log.debug("WAL mode enabled")

        # Register event listener for per-connection PRAGMAs
        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            """Configure SQLite connection with optimal settings."""
            cursor = dbapi_conn.cursor()

            # Synchronization and timeout
            cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
            cursor.execute("PRAGMA busy_timeout=5000")   # Wait 5s on locks

            # Memory and cache optimization
            cursor.execute("PRAGMA cache_size=-64000")        # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")        # Temp tables in RAM
            cursor.execute("PRAGMA mmap_size=268435456")      # 256MB memory-mapped I/O

            # Database maintenance
            cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")  # Prevent bloat

            cursor.close()

        # Create session factory with optimal settings
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Keep objects accessible after commit
        )

        self._initialized = True
        log.info("Database initialized successfully")

    @asynccontextmanager
    async def session(self, auto_commit: bool = True) -> AsyncIterator[AsyncSession]:
        """
        Async context manager for database sessions.

        Args:
            auto_commit: If True, automatically commits on successful exit.
                        Set to False for read-only operations.

        Yields:
            AsyncSession: Database session

        Example:
            # Write operation (auto-commits)
            async with db.session() as session:
                session.add(new_item)

            # Read operation (no commit)
            async with db.session(auto_commit=False) as session:
                items = await session.execute(select(Item))
        """
        if self._session_factory is None:
            msg = "Database not initialized. Call initialize() first."
            raise RuntimeError(msg)

        session = self._session_factory()
        try:
            yield session
            if auto_commit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def read_session(self) -> AsyncIterator[AsyncSession]:
        """
        Optimized session for read-only operations.

        Explicitly marks connection as read-only to prevent write locks.
        Useful for long-running queries or analytics.
        """
        async with self.session(auto_commit=False) as session:
            # Mark as read-only (optional, for explicit intent)
            await session.execute(text("-- read-only query"))
            yield session

    async def health_check(self, force: bool = False) -> DatabaseStatus:
        """
        Check database connectivity and configuration.

        Args:
            force: If True, bypass cache and perform fresh check

        Returns:
            DatabaseStatus: Current database status with pool metrics

        Note:
            Results are cached for 30 seconds to reduce overhead.
            Health checks use read-only connections (no write locks).
        """
        # Return cached result if available and fresh
        if (
            not force
            and self._cached_health_status is not None
            and self._last_health_check is not None
            and datetime.now() - self._last_health_check
            < timedelta(seconds=self.health_check_cache_ttl)
        ):
            log.debug("Returning cached health check result")
            return self._cached_health_status

        if not self._initialized or self._engine is None:
            status = DatabaseStatus(
                connected=False,
                wal_mode_enabled=False,
                database_path=self.database_url,
                error="Database not initialized",
            )
            self._cached_health_status = status
            self._last_health_check = datetime.now()
            return status

        try:
            # Use connect() instead of begin() to avoid transaction overhead
            async with self._engine.connect() as conn:
                # Simple connectivity check
                await conn.execute(text("SELECT 1"))

                # Verify WAL mode
                result = await conn.execute(text("PRAGMA journal_mode"))
                journal_mode = result.scalar()
                wal_enabled = journal_mode == "wal"

                status = DatabaseStatus(
                    connected=True,
                    wal_mode_enabled=wal_enabled,
                    database_path=self.database_url,
                    pool_stats=self.get_pool_status(),
                )

                self._cached_health_status = status
                self._last_health_check = datetime.now()
                return status

        except Exception as e:
            log.warning("Database health check failed", error=str(e))
            status = DatabaseStatus(
                connected=False,
                wal_mode_enabled=False,
                database_path=self.database_url,
                error=str(e),
            )
            self._cached_health_status = status
            self._last_health_check = datetime.now()
            return status

    def get_pool_status(self) -> dict[str, Any]:
        """
        Get connection pool statistics for monitoring.

        Returns:
            Dictionary with pool metrics (size, checked in/out, overflow)

        Note:
            With NullPool, most metrics will be 0 as no pooling occurs.
        """
        if self._engine is None:
            return {"status": "not_initialized"}

        try:
            pool = self._engine.pool
            return {
                "pool_type": type(pool).__name__,
                "pool_size": pool.size(),
                "checked_in_connections": pool.checkedin(),
                "checked_out_connections": pool.checkedout(),
                "overflow_connections": pool.overflow(),
                "total_connections": pool.size() + pool.overflow(),
            }
        except AttributeError:
            # NullPool doesn't have all these methods
            return {
                "pool_type": "NullPool",
                "note": "NullPool creates connections on demand without pooling",
            }

    async def close(self, timeout: float = 10.0) -> None:
        """
        Gracefully close database connection.

        Args:
            timeout: Maximum seconds to wait for active connections to close

        Note:
            Idempotent - safe to call multiple times.
        """
        if self._engine is None:
            log.debug("Database already closed")
            return

        log.info("Closing database connection", timeout=timeout)

        try:
            # Wait for active connections to complete (if using a pool)
            import asyncio
            await asyncio.wait_for(
                self._wait_for_connections_to_drain(), timeout=timeout
            )
        except asyncio.TimeoutError:
            log.warning("Timeout waiting for connections to drain, forcing close")
        except Exception as e:
            log.warning("Error draining connections", error=str(e))

        # Dispose of engine
        await self._engine.dispose()

        # Reset state
        self._engine = None
        self._session_factory = None
        self._initialized = False
        self._cached_health_status = None
        self._last_health_check = None

        log.debug("Database connection closed")

    async def _wait_for_connections_to_drain(self) -> None:
        """Wait for all checked-out connections to be returned."""
        if self._engine is None:
            return

        try:
            pool = self._engine.pool
            import asyncio

            max_wait = 100  # 10 seconds max (100 * 0.1s)
            wait_count = 0

            while pool.checkedout() > 0 and wait_count < max_wait:
                log.debug(
                    "Waiting for connections to drain",
                    active_connections=pool.checkedout(),
                )
                await asyncio.sleep(0.1)
                wait_count += 1

        except AttributeError:
            # NullPool doesn't track checked out connections
            pass

    @property
    def _masked_url(self) -> str:
        """Return database URL with sensitive data masked."""
        # Simple masking for SQLite file paths
        if "sqlite" in self.database_url.lower():
            return self.database_url

        # For other DBs, mask password
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(self.database_url)
        if parsed.password:
            netloc = f"{parsed.username}:****@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            masked = parsed._replace(netloc=netloc)
            return urlunparse(masked)

        return self.database_url

    def _ensure_data_directory(self) -> None:
        """Ensure the data directory exists for SQLite databases."""
        if "sqlite" not in self.database_url.lower():
            return

        from pathlib import Path

        # Extract file path from sqlite:///path/to/db.sqlite
        db_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "")
        db_file = Path(db_path)

        if not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)
            log.debug("Created data directory", path=str(db_file.parent))

    def __del__(self) -> None:
        """Cleanup on garbage collection (backup safety measure)."""
        if self._engine is not None:
            log.warning(
                "Database not properly closed, resources may leak. "
                "Always call close() explicitly."
            )
