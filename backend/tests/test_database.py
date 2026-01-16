"""Tests for the async SQLite database module.

Tests database initialization, session management, transactions,
health checks, and error handling.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.ext.declarative import declarative_base

from gitlab_queue.db.database import (
    Database,
    DatabaseAlreadyInitializedError,
    DatabaseConfigurationError,
    DatabaseNotInitializedError,
    create_database,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Sample model for testing
Base = declarative_base()


class TestModel(Base):
    __tablename__ = "test_table"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path."""
    db_file = tmp_path / "test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest_asyncio.fixture
async def database(temp_db_path: str) -> AsyncIterator[Database]:
    """Create an initialized database for testing."""
    db = Database(temp_db_path)
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


class TestDatabaseInitialization:
    """Test database initialization and configuration."""

    async def test_initialize_success(self, temp_db_path: str) -> None:
        """Test successful database initialization."""
        db = Database(temp_db_path)
        assert not db._initialized

        await db.initialize()

        assert db._initialized
        assert db._engine is not None
        assert db._session_factory is not None

        await db.close()

    async def test_initialize_twice_raises_error(self, temp_db_path: str) -> None:
        """Test that initializing twice raises an error."""
        db = Database(temp_db_path)
        await db.initialize()

        with pytest.raises(DatabaseAlreadyInitializedError):
            await db.initialize()

        await db.close()

    async def test_concurrent_initialization(self, temp_db_path: str) -> None:
        """Test that concurrent initialization attempts are handled safely."""
        db = Database(temp_db_path)

        # Simulate concurrent initialization attempts
        results = await asyncio.gather(
            db.initialize(),
            db.initialize(),
            return_exceptions=True,
        )

        # One should succeed, one should fail
        assert sum(isinstance(r, DatabaseAlreadyInitializedError) for r in results) == 1
        assert sum(r is None for r in results) == 1

        await db.close()

    async def test_path_traversal_protection(self) -> None:
        """Test protection against path traversal attacks."""
        with tempfile.TemporaryDirectory() as allowed_dir:
            # Try to create database outside allowed directory
            malicious_path = "sqlite+aiosqlite:///../../../tmp/evil.db"
            db = Database(
                malicious_path,
                allowed_base_path=allowed_dir,
            )

            with pytest.raises(DatabaseConfigurationError) as exc_info:
                await db.initialize()

            assert "outside allowed directory" in str(exc_info.value)

    async def test_context_manager(self, temp_db_path: str) -> None:
        """Test database as async context manager."""
        async with Database(temp_db_path) as db:
            assert db._initialized
            async with db.session() as session:
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1

        # Should be closed after exiting context
        assert not db._initialized


class TestDatabaseConfiguration:
    """Test database configuration and PRAGMA settings."""

    async def test_wal_mode_enabled(self, database: Database) -> None:
        """Test that WAL mode is properly enabled."""
        async with database.session() as session:
            result = await session.execute(text("PRAGMA journal_mode"))
            assert result.scalar() == "wal"

    async def test_foreign_keys_enabled(self, database: Database) -> None:
        """Test that foreign key constraints are enabled."""
        async with database.session() as session:
            result = await session.execute(text("PRAGMA foreign_keys"))
            assert result.scalar() == 1

    async def test_synchronous_full(self, database: Database) -> None:
        """Test that synchronous mode is set to FULL for durability."""
        async with database.session() as session:
            result = await session.execute(text("PRAGMA synchronous"))
            # SQLite returns 2 for FULL mode
            assert result.scalar() == 2

    async def test_busy_timeout_set(self, database: Database) -> None:
        """Test that busy timeout is properly configured."""
        async with database.session() as session:
            result = await session.execute(text("PRAGMA busy_timeout"))
            assert result.scalar() == 30000  # 30 seconds in milliseconds


class TestSessionManagement:
    """Test session creation and management."""

    async def test_session_creation(self, database: Database) -> None:
        """Test creating a database session."""
        async with database.session() as session:
            assert session is not None
            # Session should be active
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_session_without_initialization(self, temp_db_path: str) -> None:
        """Test that accessing session without initialization raises error."""
        db = Database(temp_db_path)

        with pytest.raises(DatabaseNotInitializedError):
            async with db.session():
                pass

    async def test_session_rollback_on_exception(self, database: Database) -> None:
        """Test that session rolls back on exception."""
        # Create a test table
        async with database.session() as session:
            await session.execute(
                text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, value TEXT)")
            )
            await session.commit()

        # Try to insert with exception
        with pytest.raises(ValueError):
            async with database.session() as session:
                await session.execute(text("INSERT INTO test_rollback (value) VALUES ('test')"))
                raise ValueError("Test exception")

        # Verify nothing was inserted
        async with database.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_rollback"))
            assert result.scalar() == 0

    async def test_session_uncommitted_warning(self, database: Database) -> None:
        """Test warning for uncommitted transactions."""
        # Create a test table
        async with database.session() as session:
            await session.execute(
                text("CREATE TABLE test_commit (id INTEGER PRIMARY KEY, value TEXT)")
            )
            await session.commit()

        # Insert without explicit commit (should be rolled back with warning)
        async with database.session() as session:
            await session.execute(text("INSERT INTO test_commit (value) VALUES ('uncommitted')"))
            # No commit - should trigger warning and rollback

        # Verify nothing was committed
        async with database.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_commit"))
            assert result.scalar() == 0


class TestTransactionHelper:
    """Test the transaction() context manager."""

    async def test_transaction_auto_commit(self, database: Database) -> None:
        """Test that transaction() automatically commits on success."""
        # Create a test table
        async with database.transaction() as session:
            await session.execute(
                text("CREATE TABLE test_auto_commit (id INTEGER PRIMARY KEY, value TEXT)")
            )

        # Insert with transaction (should auto-commit)
        async with database.transaction() as session:
            await session.execute(text("INSERT INTO test_auto_commit (value) VALUES ('committed')"))
            # No explicit commit needed

        # Verify data was committed
        async with database.session() as session:
            result = await session.execute(text("SELECT value FROM test_auto_commit"))
            assert result.scalar() == "committed"

    async def test_transaction_auto_rollback(self, database: Database) -> None:
        """Test that transaction() automatically rolls back on exception."""
        # Create a test table
        async with database.transaction() as session:
            await session.execute(
                text("CREATE TABLE test_auto_rollback (id INTEGER PRIMARY KEY, value TEXT)")
            )

        # Try to insert with exception (should auto-rollback)
        with pytest.raises(ValueError):
            async with database.transaction() as session:
                await session.execute(
                    text("INSERT INTO test_auto_rollback (value) VALUES ('rolled_back')")
                )
                raise ValueError("Test exception")

        # Verify nothing was committed
        async with database.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_auto_rollback"))
            assert result.scalar() == 0

    async def test_transaction_without_initialization(self, temp_db_path: str) -> None:
        """Test that transaction without initialization raises error."""
        db = Database(temp_db_path)

        with pytest.raises(DatabaseNotInitializedError):
            async with db.transaction():
                pass


class TestHealthCheck:
    """Test database health check functionality."""

    async def test_health_check_success(self, database: Database) -> None:
        """Test successful health check."""
        status = await database.health_check()

        assert status.connected is True
        assert status.wal_mode_enabled is True
        assert status.foreign_keys_enabled is True
        assert status.error is None
        # Check URL is masked
        assert "***" not in status.database_path or "@" not in status.database_path

    async def test_health_check_not_initialized(self, temp_db_path: str) -> None:
        """Test health check on uninitialized database."""
        db = Database(temp_db_path)
        status = await db.health_check()

        assert status.connected is False
        assert status.wal_mode_enabled is False
        assert status.foreign_keys_enabled is False
        assert status.error == "Database not initialized"

    async def test_health_check_after_close(self, temp_db_path: str) -> None:
        """Test health check after closing database."""
        db = Database(temp_db_path)
        await db.initialize()
        await db.close()

        status = await db.health_check()

        assert status.connected is False
        assert status.error == "Database not initialized"


class TestURLMasking:
    """Test credential masking in database URLs."""

    def test_mask_url_with_password(self) -> None:
        """Test masking URLs with passwords."""
        db = Database("postgresql+asyncpg://user:secret@localhost/db")
        assert db._masked_url == "postgresql+asyncpg://user:***@localhost/db"

    def test_mask_url_without_password(self) -> None:
        """Test URLs without passwords remain unchanged."""
        db = Database("sqlite+aiosqlite:///data/queue.db")
        assert db._masked_url == "sqlite+aiosqlite:///data/queue.db"

    def test_mask_url_complex(self) -> None:
        """Test masking complex URLs."""
        db = Database("mysql+aiomysql://admin:p@ss:w0rd@db.example.com:3306/mydb")
        # Should mask the last colon-separated part before @
        assert "***" in db._masked_url
        assert "p@ss:w0rd" not in db._masked_url


class TestCreateDatabase:
    """Test the create_database helper function."""

    async def test_create_database_helper(self, temp_db_path: str) -> None:
        """Test creating database with helper function."""
        db = await create_database(temp_db_path, echo=False)

        try:
            assert db._initialized
            async with db.session() as session:
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            await db.close()

    async def test_create_database_with_base_path(self) -> None:
        """Test creating database with allowed base path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = f"sqlite+aiosqlite:///{temp_dir}/test.db"
            db = await create_database(
                db_path,
                allowed_base_path=temp_dir,
            )

            try:
                assert db._initialized
                assert db.allowed_base_path == temp_dir
            finally:
                await db.close()


class TestEngineProperty:
    """Test the engine property accessor."""

    async def test_engine_property_initialized(self, database: Database) -> None:
        """Test accessing engine when initialized."""
        engine = database.engine
        assert engine is not None
        assert engine == database._engine

    async def test_engine_property_not_initialized(self, temp_db_path: str) -> None:
        """Test accessing engine when not initialized raises error."""
        db = Database(temp_db_path)

        with pytest.raises(DatabaseNotInitializedError):
            _ = db.engine


@pytest.mark.asyncio
async def test_integration_full_workflow(temp_db_path: str) -> None:
    """Integration test of full database workflow."""
    # Initialize database
    async with Database(temp_db_path) as db:
        # Check health
        status = await db.health_check()
        assert status.connected

        # Create table with transaction
        async with db.transaction() as session:
            await session.execute(
                text(
                    """CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL
                )"""
                )
            )

        # Insert data with explicit session management
        async with db.session() as session:
            await session.execute(
                text("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
            )
            await session.commit()

        # Query data
        async with db.session() as session:
            result = await session.execute(
                text("SELECT name FROM users WHERE email = 'alice@example.com'")
            )
            assert result.scalar() == "Alice"

        # Test rollback on constraint violation
        with pytest.raises(Exception):
            async with db.transaction() as session:
                await session.execute(
                    text("INSERT INTO users (name, email) VALUES ('Bob', 'alice@example.com')")
                )
                # Should fail due to unique constraint

        # Verify Bob wasn't inserted
        async with db.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            assert result.scalar() == 1
