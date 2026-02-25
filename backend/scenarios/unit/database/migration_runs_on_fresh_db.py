"""Test that migrations run successfully on a fresh database."""

from __future__ import annotations

import tempfile
from pathlib import Path

import vedro

from gitlab_queue.db.migrations import get_current_revision, run_migrations


class Scenario(vedro.Scenario):
    subject = "migrations run successfully on a fresh database"

    def given_fresh_database_in_temp_directory(self):
        """
        Set up a temporary directory and prepare a SQLite database path and URL for migration tests.
        
        Creates a TemporaryDirectory assigned to `self._tmp_dir`, sets `self._db_path` to the Path of a file named "test_migrations.db" inside that directory, and constructs `self._db_url` as an SQLite connection string using the aiosqlite driver (format: `sqlite+aiosqlite:///<path>`).
        """
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_migrations.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_migrations_are_run(self):
        """
        Runs database migrations against the scenario's configured database.
        
        Stores the boolean outcome in `self.result`: `True` if migrations were applied, `False` if no migrations were needed.
        """
        self.result = await run_migrations(self._db_url)

    async def then_migrations_should_be_applied(self):
        """
        Assert that migrations were applied successfully.
        
        Raises:
            AssertionError: If migrations were not applied (i.e., self.result is not True).
        """
        assert self.result is True

    async def and_current_revision_should_not_be_none(self):
        """
        Asserts that the current database migration revision exists after migrations have been run.
        
        Retrieves the current migration revision for the scenario's database URL and asserts it is not None.
        """
        revision = await get_current_revision(self._db_url)
        assert revision is not None

    async def and_running_again_should_return_false(self):
        """
        Verifies that running migrations a second time reports no new migrations were applied.
        
        Asserts that calling the migration runner again against the same database URL returns `False`, indicating there were no pending migrations.
        """
        result = await run_migrations(self._db_url)
        assert result is False

    def do_cleanup(self):
        """
        Remove the temporary directory created for the scenario.
        
        Deletes the temporary directory and its contents that were created for the test.
        """
        self._tmp_dir.cleanup()
