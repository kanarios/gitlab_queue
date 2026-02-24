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
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.complete_mr(42, "merged")

    def then_completion_should_succeed(self):
        assert self.result.success is True

    async def and_history_should_have_timing_metrics(self):
        async with self.db.session() as session:
            history_repo = HistoryRepository(session)
            history = await history_repo.get_by_iid(42)
            assert history is not None
            assert history.wait_time_seconds is not None
            assert history.wait_time_seconds > 0
            assert history.processing_time_seconds is not None
            assert history.processing_time_seconds > 0

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
