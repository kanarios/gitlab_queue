"""Test that check_migrations returns pending migration status."""

from __future__ import annotations

import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import (
    get_current_revision,
    get_pending_migrations,
    run_migrations,
)


class Scenario(vedro.Scenario):
    subject = "migration check returns pending status on fresh database"

    def given_fresh_database(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_check.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_pending_migrations_are_checked(self):
        self.pending = await get_pending_migrations(self._db_url)
        self.current_revision = await get_current_revision(self._db_url)

    def then_pending_migrations_should_not_be_empty(self):
        assert len(self.pending) > 0, "Expected pending migrations on a fresh database"

    def and_current_revision_should_be_none(self):
        assert self.current_revision is None, f"Expected no current revision on fresh DB, got {self.current_revision}"

    def and_pending_should_be_a_list_of_strings(self):
        assert isinstance(self.pending, list)
        for rev in self.pending:
            assert isinstance(rev, str), f"Expected string revision, got {type(rev)}"

    def do_cleanup(self):
        if hasattr(self, "_tmp_dir"):
            self._tmp_dir.cleanup()


class ScenarioFullyMigrated(vedro.Scenario):
    subject = "migration check returns empty list after all migrations applied"

    def given_fully_migrated_database(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_uptodate.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_migrations_are_run_and_then_checked(self):
        await run_migrations(self._db_url)
        self.pending = await get_pending_migrations(self._db_url)

    def then_pending_should_be_empty(self):
        assert len(self.pending) == 0, f"Expected no pending migrations after full run, got {self.pending}"

    def do_cleanup(self):
        if hasattr(self, "_tmp_dir"):
            self._tmp_dir.cleanup()
