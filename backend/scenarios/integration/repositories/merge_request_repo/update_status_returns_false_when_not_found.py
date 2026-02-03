"""Test that update_status returns False when MR is not found."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update_status returns false when mr not found"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_update_status_is_called_for_nonexistent_mr(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.update_status(999, "rebasing")

    def then_result_should_be_false(self):
        assert self.result is False

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
