"""Test that get_by_status filters MRs correctly."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_by_status filters merge requests correctly"

    async def given_database_with_mixed_status_mrs(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="queued")
            await seed_mr(session, iid=3, status="rebasing")
            await seed_mr(session, iid=4, status="testing")

    async def when_get_by_status_is_called_for_queued(self):
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_by_status("queued")

    def then_only_queued_mrs_should_be_returned(self):
        assert len(self.result) == 2
        iids = {mr.iid for mr in self.result}
        assert iids == {1, 2}

    async def do_cleanup(self):
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
