"""Test that add_if_not_exists returns existing MR when it already exists."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add_if_not_exists returns existing mr when already present"

    async def given_database_with_existing_mr(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            self.existing = await seed_mr(session, iid=42, title="Existing MR")

    async def when_add_if_not_exists_is_called_with_same_iid(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.add_if_not_exists(
                iid=42,
                title="New Title",
                author_name="New Author",
                author_username="newauthor",
                author_avatar=None,
                is_hotfix=False,
                labels=["merge_queue"],
                target_branch="main",
            )

    def then_result_should_be_the_existing_mr(self):
        assert self.result.iid == 42
        assert self.result.title == "Existing MR"

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
