"""Test that get_position returns None for a non-existent MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_position returns none for missing merge request"

    async def given_empty_database(self):
        """
        Initialize an isolated test SQLite database and create the required tables for the scenario.
        
        Creates the test database context, enters it to obtain a database handle, and sets up the schema used by the test.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_position_is_called_for_nonexistent_mr(self):
        """
        Calls MergeRequestRepository.get_position with a non-existent merge request ID and records the result on the scenario.
        
        Opens an asynchronous database session, invokes get_position(999) on a MergeRequestRepository instance, and assigns the returned value to self.position for later assertions.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.position = await repo.get_position(999)

    def then_position_should_be_none(self):
        """
        Asserts that the previously retrieved merge request position is None.
        
        Raises:
            AssertionError: If the stored position is not None.
        """
        assert self.position is None

    async def do_cleanup(self):
        """
        Exit the test database context and release its resources.
        
        This method finalizes the asynchronous database context previously entered for the scenario by calling the context manager's exit method, ensuring connections and related resources are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
