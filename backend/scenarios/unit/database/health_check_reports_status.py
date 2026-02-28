"""Test that health_check returns proper status dict."""

from __future__ import annotations

import vedro

from gitlab_queue.db.database import Database, DatabaseStatus
from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "health check reports proper status for initialized database"

    async def given_initialized_database(self):
        """
        Enter an initialized test database context and save the acquired Database instance on the scenario.

        This sets up an initialized test database for the scenario by creating and entering the test database context, storing the context as `self._db_ctx` and the resulting database instance as `self.db`.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_health_check_is_called(self):
        """
        Invoke the database health check and store the resulting DatabaseStatus on the scenario.
        """
        self.status = await self.db.health_check()

    def then_status_should_be_database_status_instance(self):
        """
        Asserts that the stored health check result is an instance of DatabaseStatus.

        Raises:
            AssertionError: If self.status is not an instance of DatabaseStatus.
        """
        assert isinstance(self.status, DatabaseStatus)

    def and_connected_should_be_true(self):
        """
        Assert that the last health check reported the database as connected.

        Raises:
            AssertionError: If `self.status.connected` is not True.
        """
        assert self.status.connected is True

    def and_foreign_keys_should_be_enabled(self):
        """
        Asserts that the database reports foreign key enforcement as enabled.

        Raises:
            AssertionError: if `status.foreign_keys_enabled` is not True.
        """
        assert self.status.foreign_keys_enabled is True

    def and_error_should_be_none(self):
        """
        Asserts that the database health check reported no error.

        Raises:
            AssertionError: If `self.status.error` is not None.
        """
        assert self.status.error is None

    def and_database_path_should_be_present(self):
        """
        Asserts that the health check result contains a non-empty database path.
        """
        assert self.status.database_path is not None
        assert len(self.status.database_path) > 0

    async def do_cleanup(self):
        """
        Exit the initialized database context and release its resources.

        This finalizer exits the async context obtained from initialized_test_database(), ensuring the test database is closed and any associated resources are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)


class Scenario2(vedro.Scenario):
    subject = "health check reports not initialized for fresh database"

    def given_uninitialized_database(self):
        """
        Create an uninitialized in-memory SQLite Database instance and assign it to self.db.
        """
        self.db = Database(database_url="sqlite+aiosqlite:///:memory:")

    async def when_health_check_is_called(self):
        """
        Invoke the database health check and store the resulting DatabaseStatus on the scenario.
        """
        self.status = await self.db.health_check()

    def then_connected_should_be_false(self):
        """
        Assert that the health check reports the database as not connected.

        Raises:
            AssertionError: If `status.connected` is True.
        """
        assert self.status.connected is False

    def and_error_should_mention_not_initialized(self):
        assert self.status.error is not None
        assert "not initialized" in self.status.error.lower()

    async def do_cleanup(self):
        """
        Close the scenario's database connection.

        This performs cleanup by closing the Database instance stored on the scenario.
        """
        await self.db.close()
