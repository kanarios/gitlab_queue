"""Test that get_next_queued returns None when no queued MRs exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_next_queued returns none when queue is empty"

    async def given_empty_database(self):
        """
        Prepare an initialized empty test database and create required tables for the scenario.
        
        Creates an initialized test database context, enters it to obtain a database handle stored on self.db, and invokes create_tables to set up the schema. The database context object is stored on self._db_ctx for later cleanup.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_next_queued_is_called(self):
        """
        Invokes MergeRequestRepository.get_next_queued and stores the outcome on the scenario.
        
        Sets self.result to the next queued merge request object, or None if no queued merge requests exist.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.get_next_queued()

    def then_result_should_be_none(self):
        """
        Assert that the previously obtained result is None.
        
        Raises:
            AssertionError: If self.result is not None.
        """
        assert self.result is None

    async def do_cleanup(self):
        """
        Exit the asynchronous database context to release test resources.
        
        Performs the async context manager exit for the test database created in setup, ensuring connections and temporary resources are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
