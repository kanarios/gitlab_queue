"""Test that session rolls back on error during a transaction."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from sqlalchemy import text


class Scenario(vedro.Scenario):
    subject = "session rolls back on error during transaction"

    async def given_initialized_database_with_table(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        # Create a test table
        async with self.db.session() as session:
            await session.execute(text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, value TEXT)"))
            await session.commit()

    async def when_session_raises_error_after_insert(self):
        self.error_caught = False
        try:
            async with self.db.session() as session:
                await session.execute(text("INSERT INTO test_rollback (id, value) VALUES (1, 'should_rollback')"))
                raise ValueError("Intentional error to trigger rollback")
        except ValueError:
            self.error_caught = True

    async def then_error_should_be_propagated(self):
        assert self.error_caught, "ValueError should have been caught"

    async def and_inserted_row_should_not_exist(self):
        async with self.db.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_rollback WHERE value = 'should_rollback'"))
            count = result.scalar()
            assert count == 0, f"Expected 0 rows after rollback, got {count}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
