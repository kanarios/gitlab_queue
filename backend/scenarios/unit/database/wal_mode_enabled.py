"""Test that WAL mode is enabled during database initialization."""

from __future__ import annotations

import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.database import Database


class Scenario(vedro.Scenario):
    subject = "WAL mode is enabled during database initialization"

    async def given_database_with_file_backend(self):
        """
        Prepare a file-backed Database instance in a temporary directory for testing.

        Creates a temporary directory, constructs a SQLite URL using aiosqlite pointing to test.db inside that directory, and stores the created objects on the instance:
        - self._tmp_dir: TemporaryDirectory object
        - self._db_path: Path to the database file
        - self._db_url: database URL string
        - self.db: instantiated Database configured with the file-backed URL
        """
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self.db = Database(database_url=self._db_url)

    async def when_database_is_initialized(self):
        """
        Initialize the Database instance and record its health status on the scenario.

        Sets `self.status` to the result of the database health check performed after initialization.
        """
        await self.db.initialize()
        self.status = await self.db.health_check()

    def then_wal_mode_should_be_enabled(self):
        """
        Assert that the database is operating in WAL (Write-Ahead Logging) mode.

        Raises:
            AssertionError: if `self.status.wal_mode_enabled` is not True.
        """
        assert self.status.wal_mode_enabled

    def and_database_should_be_connected(self):
        """
        Assert that the database connection is established.

        Raises:
            AssertionError: If the database is not connected (i.e., `self.status.connected` is false).
        """
        assert self.status.connected

    async def do_cleanup(self):
        """
        Close the Database connection and remove the temporary test directory.
        """
        await self.db.close()
        self._tmp_dir.cleanup()
