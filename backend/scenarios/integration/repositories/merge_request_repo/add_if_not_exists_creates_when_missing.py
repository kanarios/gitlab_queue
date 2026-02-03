"""Test that add_if_not_exists creates a new MR when it does not exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add_if_not_exists creates new mr when missing"

    async def given_empty_database(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_add_if_not_exists_is_called(self):
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.result = await repo.add_if_not_exists(
                iid=42,
                title="New MR",
                author_name="Test User",
                author_username="testuser",
                author_avatar=None,
                is_hotfix=False,
                labels=["merge_queue"],
                target_branch="main",
            )

    def then_result_should_be_the_new_mr(self):
        assert self.result.iid == 42
        assert self.result.title == "New MR"
        assert self.result.status == "queued"

    async def and_mr_should_be_in_database(self):
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
