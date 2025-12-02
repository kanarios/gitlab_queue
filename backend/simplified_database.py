"""Simplified database module - 77 lines vs original 130 lines."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Database:
    """Async SQLite database connection with WAL mode."""

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.engine = engine
        self._session_factory = session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session. Automatically rolls back on error."""
        async with self._session_factory() as session:
            yield session

    async def close(self) -> None:
        """Close database connection and dispose of engine."""
        await self.engine.dispose()

    async def __aenter__(self) -> Database:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()


async def create_database(database_url: str, *, echo: bool = False) -> Database:
    """Create and initialize a database connection.

    Args:
        database_url: SQLite URL (e.g., "sqlite+aiosqlite:///data/db.sqlite")
        echo: Whether to log SQL statements

    Returns:
        Initialized Database instance ready for use

    Example:
        async with await create_database("sqlite+aiosqlite:///data/db.sqlite") as db:
            async with db.session() as session:
                result = await session.execute(text("SELECT 1"))
    """
    # Ensure parent directory exists for file-based databases
    if ":///" in database_url:
        db_path = Path(database_url.split(":///")[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine with SQLite-specific settings
    engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=echo,
    )

    # Enable WAL mode for better concurrency
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return Database(engine, session_factory)
