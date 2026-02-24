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
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.complete_mr(42, "merged")

    def then_completion_should_succeed(self):
        assert self.result.success is True
        assert self.result.history_id is not None

    async def and_mr_should_be_gone_from_active_queue(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is None

    async def and_mr_should_be_in_history(self):
        async with self.db.session() as session:
            history_repo = HistoryRepository(session)
            history = await history_repo.get_by_iid(42)
            assert history is not None
            assert history.status == "merged"
            assert history.iid == 42

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
