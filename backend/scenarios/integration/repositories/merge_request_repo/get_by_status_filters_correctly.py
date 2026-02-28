"""Test that get_by_status filters MRs correctly."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_status filters merge requests correctly"

    async def given_database_with_mixed_status_mrs(self):
        """
        Prepare a test SQLite database, create required tables, and seed four merge requests with mixed statuses.

        Sets up an asynchronous test database context and assigns it to self._db_ctx and self.db, creates the schema, and inserts four merge requests with the following (iid, status) pairs: (1, "queued"), (2, "queued"), (3, "rebasing"), (4, "testing").
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="queued")
            await seed_mr(session, iid=3, status="rebasing")
            await seed_mr(session, iid=4, status="testing")

    async def when_get_by_status_is_called_for_queued(self):
        """
        Query the MergeRequestRepository for merge requests with status "queued" and store the results.

        Opens a database session, calls get_by_status("queued") on a MergeRequestRepository instance, and assigns the returned list of merge requests to self.result.
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_by_status("queued")

    def then_only_queued_mrs_should_be_returned(self):
        """
        Asserts that the stored query result contains exactly two merge requests with iids 1 and 2.

        Raises:
            AssertionError: If the number of results is not 2 or the set of returned iids is not {1, 2}.
        """
        assert len(self.result) == 2
        iids = {mr.iid for mr in self.result}
        assert iids == {1, 2}

    async def do_cleanup(self):
        """
        Tear down and exit the database and session asynchronous contexts.

        Exits the session and database context managers opened by the scenario to release resources and ensure clean state after the test.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
