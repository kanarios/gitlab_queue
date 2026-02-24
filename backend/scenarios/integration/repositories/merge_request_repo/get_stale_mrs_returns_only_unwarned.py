"""Test that get_stale_mrs returns only unwarned stale MRs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_stale_mrs returns only unwarned stale merge requests"

    async def given_database_with_stale_mrs(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()

        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=1,
                status="queued",
                queued_at=old_time,
                stale_warning_sent=0,
            )
            await seed_mr(
                session,
                iid=2,
                status="queued",
                queued_at=old_time,
                stale_warning_sent=1,
            )

    async def when_get_stale_mrs_is_called(self):
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_stale_mrs(1)

    def then_only_unwarned_stale_mr_should_be_returned(self):
        assert len(self.result) == 1
        assert self.result[0].iid == 1
        assert self.result[0].stale_warning_sent == 0

    async def do_cleanup(self):
        if hasattr(self, "_session_ctx"):
            await self._session_ctx.__aexit__(None, None, None)
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
