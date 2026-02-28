"""Test that UnitOfWork rolls back on exception."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import (
    create_tables,
    create_test_mr_model,
)

from gitlab_queue.db.repositories import MergeRequestRepository, UnitOfWork


class Scenario(vedro.Scenario):
    subject = "unit of work rolls back on exception"

    async def given_initialized_database(self):
        """
        Initialize an asynchronous test database context and create the required tables for the scenario.

        Sets self._db_ctx to the asynchronous database context manager and self.db to the active database connection, then creates the schema tables needed by the test.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_exception_occurs_inside_uow(self):
        """
        Simulate an exception occurring inside a UnitOfWork to trigger rollback.

        Attempts to add a test MergeRequest within an auto-committing UnitOfWork, raises a ValueError to simulate failure, and stores the caught exception on self.caught_exc for later assertions about rollback behavior.
        """
        try:
            async with UnitOfWork(self.db, auto_commit=True) as uow:
                mr = create_test_mr_model(iid=42, title="Should Not Persist")
                await uow.merge_requests.add(mr)
                raise ValueError("Simulated failure")
        except ValueError as exc:
            self.caught_exc = exc

    def then_caught_exception_is_simulated_failure(self):
        """
        Assert that the previously caught exception has the message "Simulated failure".

        Raises:
            AssertionError: If the exception message is not "Simulated failure".
        """
        assert str(self.caught_exc) == "Simulated failure"

    async def and_mr_should_not_be_persisted(self):
        """
        Verify that no MergeRequest with iid 42 exists in the database.

        Queries the MergeRequestRepository for iid 42 and asserts that the query returns `None`.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is None

    async def do_cleanup(self):
        """
        Exit the test database context and release associated resources.

        This finalizer exits the asynchronous database context created during setup, ensuring connections and temporary test state are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
