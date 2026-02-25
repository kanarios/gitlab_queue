"""Test that count_active returns correct count of active MRs."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "count_active returns correct count of active merge requests"

    async def given_database_with_active_and_terminal_mrs(self):
        """
        Prepare a test database and seed it with active and terminal merge requests.
        
        Creates and enters an initialized test database context, creates required tables, and inserts three merge requests:
        iid=1 (status "queued"), iid=2 (status "rebasing"), and iid=3 (status "merged").
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="rebasing")
            await seed_mr(session, iid=3, status="merged")

    async def when_count_active_is_called(self):
        """
        Call MergeRequestRepository.count_active and store the resulting active merge request count in self.count.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.count = await repo.count_active()

    def then_count_should_be_2(self):
        """
        Assert that the stored merge request count equals two.
        
        Raises:
            AssertionError: If the previously recorded `self.count` is not 2; the message indicates the actual value.
        """
        assert self.count == 2, f"Expected 2 active MRs, got {self.count}"

    async def do_cleanup(self):
        """
        Exit and clean up the test database context used by the scenario.
        
        This awaits the asynchronous context manager teardown created during test setup to release resources and restore state.
        """
        await self._db_ctx.__aexit__(None, None, None)
