"""Test that get_by_iid returns None when MR does not exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_iid returns none when mr not found"

    async def given_empty_database(self):
        """
        Prepare an empty test database and create the required tables for the scenario.

        Stores the async database context manager on `self._db_ctx` and the opened database handle on `self.db`.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_get_by_iid_is_called_for_nonexistent_mr(self):
        """
        Calls the merge request repository to fetch an MR with iid 999 and stores the lookup result on self.result.

        This step performs a repository lookup for a non-existent merge request identifier and records the returned value for subsequent assertions.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.get_by_iid(999)

    def then_result_should_be_none(self):
        """
        Asserts that the previously fetched merge request is None.

        Raises:
            AssertionError: If `self.result` is not `None`.
        """
        assert self.result is None

    async def do_cleanup(self):
        """
        Exit the test database asynchronous context to release resources.

        Performs the async context exit for the previously entered database context manager created during setup.
        """
        await self._db_ctx.__aexit__(None, None, None)
