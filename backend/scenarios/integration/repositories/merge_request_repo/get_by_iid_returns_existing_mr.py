"""Test that get_by_iid returns an existing MR."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_iid returns existing merge request"

    async def given_database_with_mr(self):
        """
        Set up an initialized test database, create required tables, and seed a merge request with iid 42 and title "Test MR".
        
        Stores the async database context on self._db_ctx and the active database connection on self.db, then inserts the merge request within a transaction for later test use.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, title="Test MR")

    async def when_get_by_iid_is_called(self):
        """
        Call the merge request repository to fetch the merge request with IID 42 and store the result on the scenario.
        
        Opens a session context, constructs a MergeRequestRepository for that session, and assigns the fetched MergeRequest (or `None` if not found) to `self.result`.
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_by_iid(42)

    def then_result_should_be_the_mr(self):
        """
        Asserts that the fetched result corresponds to the seeded merge request with iid 42 and title "Test MR".
        
        Verifies that `self.result` is not None, that `self.result.iid` equals 42, and that `self.result.title` equals "Test MR".
        """
        assert self.result is not None
        assert self.result.iid == 42
        assert self.result.title == "Test MR"

    async def do_cleanup(self):
        """
        Exit and clean up the session and database async context managers used by the scenario.
        
        Asynchronously closes the active session context and then the database context to release resources and finalize cleanup.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
