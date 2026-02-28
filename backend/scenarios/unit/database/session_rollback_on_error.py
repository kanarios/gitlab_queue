"""Test that session rolls back on error during a transaction."""

from __future__ import annotations

import vedro
from sqlalchemy import text

from scenarios.contexts.sqlite_client import initialized_test_database


class Scenario(vedro.Scenario):
    subject = "session rolls back on error during transaction"

    async def given_initialized_database_with_table(self):
        """
        Initialize a test database context and create the table used for rollback testing.

        Sets self._db_ctx to the database context returned by initialized_test_database() and sets self.db to the entered database object. Creates the table `test_rollback` with columns `id INTEGER PRIMARY KEY` and `value TEXT`.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        # Create a test table
        async with self.db.session() as session:
            await session.execute(text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, value TEXT)"))
            await session.commit()

    async def when_session_raises_error_after_insert(self):
        """
        Performs an insert inside a session, intentionally raises an error to trigger a transaction rollback, and records that the error was caught.

        Inserts a row into the test_rollback table within an active session, raises a ValueError to cause the session transaction to roll back, and sets self.error_caught to True when the ValueError is caught.
        """
        self.error_caught = False
        try:
            async with self.db.session() as session:
                await session.execute(text("INSERT INTO test_rollback (id, value) VALUES (1, 'should_rollback')"))
                raise ValueError("Intentional error to trigger rollback")
        except ValueError:
            self.error_caught = True

    async def then_error_should_be_propagated(self):
        """
        Asserts that the intentional error raised during the session was propagated and caught.

        Raises:
            AssertionError: If the error was not propagated (i.e., the error was not caught).
        """
        assert self.error_caught

    async def and_inserted_row_should_not_exist(self):
        """
        Assert that no row with value 'should_rollback' exists in the test_rollback table.

        Checks the count of rows where value = 'should_rollback' and raises AssertionError if the count is not 0.
        """
        async with self.db.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_rollback WHERE value = 'should_rollback'"))
            count = result.scalar()
            assert count == 0

    async def do_cleanup(self):
        """
        Exit the database context and release any associated resources for the test.

        This awaits the asynchronous context manager exit on self._db_ctx to ensure the
        test database is properly torn down after the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
