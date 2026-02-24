"""Test that get_next_queued returns the first queued MR by priority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_next_queued returns first queued mr by priority"

    async def given_database_with_queued_mrs(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=10,
                status="queued",
                queued_at=(now - timedelta(minutes=5)).isoformat(),
            )
            await seed_mr(
                session,
                iid=20,
                status="queued",
                queued_at=(now - timedelta(minutes=10)).isoformat(),
            )

    async def when_get_next_queued_is_called(self):
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_next_queued()

    def then_result_should_be_the_oldest_queued_mr(self):
        assert self.result is not None
        assert self.result.iid == 20, "Should return the MR with earliest queued_at"

    async def do_cleanup(self):
        if hasattr(self, "_session_ctx"):
            await self._session_ctx.__aexit__(None, None, None)
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
