"""Test that get_position returns the correct 1-indexed position."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_position returns correct 1-indexed position"

    async def given_database_with_ordered_mrs(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=1,
                status="queued",
                queued_at=(now - timedelta(minutes=30)).isoformat(),
            )
            await seed_mr(
                session,
                iid=2,
                status="queued",
                queued_at=(now - timedelta(minutes=20)).isoformat(),
            )
            await seed_mr(
                session,
                iid=3,
                status="queued",
                queued_at=(now - timedelta(minutes=10)).isoformat(),
            )

    async def when_get_position_is_called_for_second_mr(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.position = await repo.get_position(2)

    def then_position_should_be_2(self):
        assert self.position == 2, f"Expected position 2, got {self.position}"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
