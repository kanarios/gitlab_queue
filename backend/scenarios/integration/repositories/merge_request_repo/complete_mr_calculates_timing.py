"""Test that complete_mr calculates timing metrics correctly."""

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
    subject = "complete_mr calculates wait and processing time"

    async def given_database_with_timed_mr(self):
        """
        Prepare a test SQLite database, create necessary tables, and seed a merge request (IID 42) with queued and started timestamps.
        
        Seeds the database with a merge request having status "merging" and sets self.queued_at to ~10 minutes before now and self.started_at to ~5 minutes before now for use in subsequent test steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        self.queued_at = now - timedelta(minutes=10)
        self.started_at = now - timedelta(minutes=5)

        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=42,
                status="merging",
                queued_at=self.queued_at.isoformat(),
                started_at=self.started_at.isoformat(),
            )

    async def when_complete_mr_is_called(self):
        """
        Invokes completion of the merge request with IID 42 using status "merged" and stores the operation result on self.result.
        
        Performs the repository call to complete the MR and preserves the returned result for later assertions.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.complete_mr(42, "merged")

    def then_completion_should_succeed(self):
        """
        Asserts that the previously invoked merge request completion reported success.
        
        Raises:
            AssertionError: If the completion did not succeed (`self.result.success` is not True).
        """
        assert self.result.success is True

    async def and_history_should_have_timing_metrics(self):
        """
        Verify that the history record for IID 42 contains positive wait and processing time metrics.
        
        Fetches the history by IID 42 and asserts that `wait_time_seconds` and `processing_time_seconds` are present and greater than 0.
        """
        async with self.db.session() as session:
            history_repo = HistoryRepository(session)
            history = await history_repo.get_by_iid(42)
            assert history is not None
            assert history.wait_time_seconds is not None
            assert history.wait_time_seconds > 0
            assert history.processing_time_seconds is not None
            assert history.processing_time_seconds > 0

    async def do_cleanup(self):
        """
        Exit the test database context and release its resources.
        
        Awaits the stored async context manager to close the database session and perform cleanup.
        """
        await self._db_ctx.__aexit__(None, None, None)
