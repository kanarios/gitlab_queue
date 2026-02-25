"""Test that update_status sets timestamps automatically."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update_status sets started_at timestamp automatically"

    async def given_database_with_queued_mr(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, status="queued")

    async def when_status_is_updated_to_rebasing(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.updated = await repo.update_status(42, "rebasing")

    def then_update_should_succeed(self):
        assert self.updated is True

    async def and_started_at_should_be_set(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is not None
            assert mr.status == "rebasing"
            assert mr.started_at is not None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
