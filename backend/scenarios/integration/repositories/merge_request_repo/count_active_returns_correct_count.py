"""Test that count_active returns correct count of active MRs."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "count_active returns correct count of active merge requests"

    async def given_database_with_active_and_terminal_mrs(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="rebasing")
            await seed_mr(session, iid=3, status="merged")

    async def when_count_active_is_called(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.count = await repo.count_active()

    def then_count_should_be_2(self):
        assert self.count == 2, f"Expected 2 active MRs, got {self.count}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
