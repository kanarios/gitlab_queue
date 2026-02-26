"""Test that PRAGMA foreign_keys=ON is set during database initialization."""

from __future__ import annotations

import vedro

from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "foreign keys are enabled during database initialization"

    async def given_initialized_database(self):
        """
        Initialize and enter a test database context and store the context manager and database object on the instance.

        Sets self._db_ctx to the context manager returned by initialized_test_database() and self.db to the entered database connection/object for use by subsequent steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()

    async def when_health_check_is_performed(self):
        """
        Performs a health check on the initialized database and stores the result.

        Stores the result of calling the database's health_check() in self.status.
        """
        self.status = await self.db.health_check()

    def then_foreign_keys_should_be_enabled(self):
        """
        Check that the database reports SQLite foreign key enforcement is enabled.

        Raises:
            AssertionError: If `self.status.foreign_keys_enabled` is not True.
        """
        assert self.status.foreign_keys_enabled is True

    def and_database_should_be_connected(self):
        """
        Verify the initialized database reports an active connection.

        Raises:
            AssertionError: If the database health status indicates it is not connected.
        """
        assert self.status.connected is True

    async def do_cleanup(self):
        """
        Exit the asynchronous database context to close the initialized test database.

        Ensures the scenario's database context is properly closed by awaiting the context manager's teardown.
        """
        await self._db_ctx.__aexit__(None, None, None)
