"""Test that migrations run successfully on a fresh database."""

from __future__ import annotations

import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import get_current_revision, run_migrations


class Scenario(vedro.Scenario):
    subject = "migrations run successfully on a fresh database"

    def given_fresh_database_in_temp_directory(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_migrations.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_migrations_are_run(self):
        self.result = await run_migrations(self._db_url)

    async def then_migrations_should_be_applied(self):
        assert self.result is True

    async def and_current_revision_should_not_be_none(self):
        revision = await get_current_revision(self._db_url)
        assert revision is not None

    async def and_running_again_should_return_false(self):
        result = await run_migrations(self._db_url)
        assert result is False

    def do_cleanup(self):
        self._tmp_dir.cleanup()
