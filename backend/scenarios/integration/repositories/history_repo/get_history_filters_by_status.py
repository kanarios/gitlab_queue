"""Test that get_history filters by status."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_history filters by status"

    async def given_database_with_mixed_status_history(self):
        """
        Prepare a test database with history records of mixed statuses and store the database context and session on the scenario.

        Creates necessary tables and seeds four history records with iids 1-4 and statuses "merged", "merged", "failed", and "conflict". Sets self._db_ctx to the initialized database context and self.db to the entered database session.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_history(session, iid=1, status="merged")
            await seed_history(session, iid=2, status="merged")
            await seed_history(session, iid=3, status="failed")
            await seed_history(session, iid=4, status="conflict")

    async def when_get_history_is_called_with_status_filter(self):
        """
        Call HistoryRepository.get_history with a "merged" status filter and store the returned result on the scenario.

        This obtains an async database session, instantiates HistoryRepository with that session, invokes get_history(status_filter="merged"), and assigns the response to self.result for later assertions.
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = HistoryRepository(session)
        self.result = await repo.get_history(status_filter="merged")

    def then_only_merged_records_should_be_returned(self):
        """
        Assert that the history query returned exactly two items and all have status "merged".

        Raises:
            AssertionError: If the total number of results is not 2 or any returned item's status is not "merged".
        """
        assert self.result.total == 2
        for item in self.result.items:
            assert item.status == "merged"

    async def do_cleanup(self):
        """
        Exit and release the database and session asynchronous context managers used by the scenario.

        Closes the session context and then the database context to ensure connections and resources are cleaned up.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
