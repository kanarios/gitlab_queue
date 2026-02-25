"""Test that add_if_not_exists creates a new MR when it does not exist."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "add_if_not_exists creates new mr when missing"

    async def given_empty_database(self):
        """
        Set up an initialized test database and create the required tables for the scenario.
        
        Stores the async database context on self._db_ctx and the acquired database handle on self.db, ensuring the schema is created before the test proceeds.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

    async def when_add_if_not_exists_is_called(self):
        """
        Adds a merge request with IID 42 to the repository and saves the returned MergeRequest object on the scenario as self.result.
        
        The created merge request uses title "New MR", author name "Test User", author username "testuser", no author avatar, is not a hotfix, has labels ["merge_queue"], and targets the "main" branch.
        """
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
        """
        Asserts that the created merge request has IID 42, title "New MR", and status "queued".
        """
        assert self.result.iid == 42
        assert self.result.title == "New MR"
        assert self.result.status == "queued"

    async def and_mr_should_be_in_database(self):
        """
        Asserts that a merge request with IID 42 exists in the database.
        
        Verifies that a lookup for IID 42 returns a non-None merge request record.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is not None

    async def do_cleanup(self):
        """
        Close the database test context used by the scenario.
        
        Exits the asynchronous database context manager created in setup, ensuring the in-memory test database and related resources are released.
        """
        await self._db_ctx.__aexit__(None, None, None)
