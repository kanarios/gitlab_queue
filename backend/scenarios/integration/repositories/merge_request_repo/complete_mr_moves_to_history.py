"""Test that complete_mr moves MR from active queue to history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import (
    HistoryRepository,
    MergeRequestRepository,
)


class Scenario(vedro.Scenario):
    subject = "complete_mr moves merge request to history"

    async def given_database_with_active_mr(self):
        """
        Prepare a test SQLite database, store its async context on the instance, create required tables, and seed it with an active merge request (iid 42) having status "merging" and timestamps: queued_at = 10 minutes ago, started_at = 5 minutes ago.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=42,
                status="merging",
                queued_at=(now - timedelta(minutes=10)).isoformat(),
                started_at=(now - timedelta(minutes=5)).isoformat(),
            )

    async def when_complete_mr_is_called(self):
        """
        Invoke the merge-request repository to mark MR with iid 42 as merged and store the operation result on the scenario.
        
        The repository call's return value is assigned to self.result for later assertions.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.complete_mr(42, "merged")

    def then_completion_should_succeed(self):
        """
        Asserts that completing the merge request reported success and produced a history identifier.
        
        Verifies that `self.result.success` is True and `self.result.history_id` is not None.
        """
        assert self.result.success is True
        assert self.result.history_id is not None

    async def and_mr_should_be_gone_from_active_queue(self):
        """
        Asserts that the merge request with IID 42 is no longer present in the active queue.
        
        Opens a database session, queries the active merge requests repository for IID 42, and asserts the result is None.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is None

    async def and_mr_should_be_in_history(self):
        """
        Asserts that a history record exists for merge request IID 42 with status "merged".
        
        Performs a database lookup for a history entry with iid 42 and asserts that the entry is present, its `status` equals "merged", and its `iid` equals 42.
        """
        async with self.db.session() as session:
            history_repo = HistoryRepository(session)
            history = await history_repo.get_by_iid(42)
            assert history is not None
            assert history.status == "merged"
            assert history.iid == 42

    async def do_cleanup(self):
        """
        Clean up and close the test database context created during the scenario setup.
        
        This exits the asynchronous database context to release resources opened for testing.
        """
        await self._db_ctx.__aexit__(None, None, None)
