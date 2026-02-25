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
        """
        Prepare a fresh temporary SQLite database for the scenario.
        
        Sets the following attributes on self:
        - _tmp_dir: a tempfile.TemporaryDirectory instance managing the temp directory.
        - _db_path: a pathlib.Path pointing to the database file inside the temp directory.
        - _db_url: a SQLite connection URL string using the aiosqlite driver.
        """
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_check.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_pending_migrations_are_checked(self):
        """
        Fetch pending migrations and the current migration revision for the scenario's database.
        
        Stores the list of pending migration identifiers on self.pending and the current revision (or None) on self.current_revision.
        """
        self.pending = await get_pending_migrations(self._db_url)
        self.current_revision = await get_current_revision(self._db_url)

    def then_pending_migrations_should_not_be_empty(self):
        """
        Check that the recorded pending migrations list contains at least one entry.
        """
        assert len(self.pending) > 0

    def and_current_revision_should_be_none(self):
        """
        Asserts that the database has no current migration revision.
        
        Raises:
            AssertionError: If self.current_revision is not None.
        """
        assert self.current_revision is None

    def and_pending_should_be_a_list_of_strings(self):
        """
        Asserts that self.pending is a list where every item is a string.
        
        Raises:
            AssertionError: if self.pending is not a list or any element is not a `str`.
        """
        assert isinstance(self.pending, list)
        for rev in self.pending:
            assert isinstance(rev, str)

    def do_cleanup(self):
        """
        Remove temporary directory created for the scenario.
        
        Performs cleanup of filesystem resources allocated during the scenario by removing the temporary directory.
        """
        self._tmp_dir.cleanup()


class ScenarioFullyMigrated(vedro.Scenario):
    subject = "migration check returns empty list after all migrations applied"

    def given_fully_migrated_database(self):
        """
        Prepare a temporary SQLite database file and store its path and connection URL on the instance for use in tests.
        
        Sets:
            _tmp_dir (tempfile.TemporaryDirectory): Temporary directory holding the database file.
            _db_path (Path): Filesystem path to the temporary SQLite database file.
            _db_url (str): SQLAlchemy-compatible database URL using the aiosqlite driver (format: sqlite+aiosqlite:///...).
        """
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_uptodate.db"
        self._db_url = f"sqlite+aiosqlite:///{self._db_path}"

    async def when_migrations_are_run_and_then_checked(self):
        """
        Apply all database migrations and record remaining pending migrations on the scenario.
        
        Stores the list of pending migration identifiers in self.pending.
        """
        await run_migrations(self._db_url)
        self.pending = await get_pending_migrations(self._db_url)

    def then_pending_should_be_empty(self):
        """
        Asserts that there are no pending database migrations.
        
        Raises an AssertionError if the stored `self.pending` list has a length greater than zero.
        """
        assert len(self.pending) == 0

    def do_cleanup(self):
        """
        Remove temporary directory created for the scenario.
        
        Performs cleanup of filesystem resources allocated during the scenario by removing the temporary directory.
        """
        self._tmp_dir.cleanup()
