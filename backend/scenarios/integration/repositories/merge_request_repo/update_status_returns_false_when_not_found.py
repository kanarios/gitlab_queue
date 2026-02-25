"""Test that update_status returns False when MR is not found."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update_status returns false when mr not found"

    async def given_empty_database(self):
        """
        Prepare an empty test database for the scenario and create required tables.
        
        Sets:
            self._db_ctx: asynchronous test database context manager returned by initialized_test_database().
            self.db: active database session/connection entered from the context manager.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_update_status_is_called_for_nonexistent_mr(self):
        """
        Invokes the repository to update the status of a non-existent merge request and saves the outcome to self.result.
        
        Calls MergeRequestRepository.update_status with MR id 999 and status "rebasing" inside a database transaction and assigns the returned boolean to self.result.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.update_status(999, "rebasing")

    def then_result_should_be_false(self):
        """
        Asserts that the stored result is False.
        
        Raises:
            AssertionError: If self.result is not False.
        """
        assert self.result is False

    async def do_cleanup(self):
        """
        Exit the asynchronous test database context used by the scenario.
        
        Closes the previously entered async database context to release connections and resources.
        """
        await self._db_ctx.__aexit__(None, None, None)
