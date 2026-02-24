"""Test that count_by_status returns correct grouped counts."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "count_by_status returns grouped counts for active states"

    async def given_database_with_various_statuses(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="queued")
            await seed_mr(session, iid=3, status="rebasing")
            await seed_mr(session, iid=4, status="testing")
            await seed_mr(session, iid=5, status="merged")

    async def when_count_by_status_is_called(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.counts = await repo.count_by_status()

    def then_counts_should_reflect_active_statuses(self):
        assert self.counts["queued"] == 2
        assert self.counts["rebasing"] == 1
        assert self.counts["testing"] == 1
        assert self.counts["merging"] == 0

    def and_terminal_statuses_should_not_be_included(self):
        assert "merged" not in self.counts

    async def do_cleanup(self):
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
