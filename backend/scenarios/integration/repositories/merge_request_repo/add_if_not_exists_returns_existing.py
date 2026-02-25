"""Test that add_if_not_exists returns existing MR when it already exists."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add_if_not_exists returns existing mr when already present"

    async def given_database_with_existing_mr(self):
        """
        Prepare an isolated test database, create required tables, and seed it with an existing merge request (iid=42, title "Existing MR").
        
        Stores the async database context on `self._db_ctx`, the opened database connection on `self.db`, and the seeded merge request on `self.existing` for use by subsequent test steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            self.existing = await seed_mr(session, iid=42, title="Existing MR")

    async def when_add_if_not_exists_is_called_with_same_iid(self):
        """
        Invokes MergeRequestRepository.add_if_not_exists with iid 42 and new metadata, storing the returned merge request on self.result.
        
        Executes the repository call inside a database transaction using a session from self.db.
        """
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
        """
        Verify that the repository returned the pre-existing merge request with iid 42 and title "Existing MR".
        
        Asserts that self.result.iid is 42 and self.result.title is "Existing MR".
        """
        assert self.result.iid == 42
        assert self.result.title == "Existing MR"

    async def do_cleanup(self):
        """
        Exit the test database context and release its resources.
        
        Performs the asynchronous context manager exit to clean up the initialized database used by the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
