"""Test that WAL mode is enabled during database initialization."""

from __future__ import annotations

import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.database import Database


class Scenario(vedro.Scenario):
    subject = "WAL mode is enabled during database initialization"

    async def given_database_with_file_backend(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"
        self.db = Database(database_url=self._db_url)

    async def when_database_is_initialized(self):
        await self.db.initialize()
        self.status = await self.db.health_check()

    def then_wal_mode_should_be_enabled(self):
        assert self.status.wal_mode_enabled, (
            f"Expected WAL mode to be enabled, got journal_mode check: {self.status.wal_mode_enabled}"
        )

    def and_database_should_be_connected(self):
        assert self.status.connected, "Database should be connected after initialization"

    async def do_cleanup(self):
        if hasattr(self, "db"):
            await self.db.close()
        if hasattr(self, "_tmp_dir"):
            self._tmp_dir.cleanup()
