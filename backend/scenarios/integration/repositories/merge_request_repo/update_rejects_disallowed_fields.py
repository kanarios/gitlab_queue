"""Test that update rejects disallowed fields."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update rejects disallowed fields like title"

    async def given_database_with_mr(self):
        """
        Set up an initialized test database, create required tables, and seed it with a merge request (iid 42, title "Original Title").
        
        This method initializes the test database context, opens the database connection, creates the schema, and inserts a seeded merge request used by subsequent steps in the scenario.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, title="Original Title")

    async def when_update_is_called_with_disallowed_field(self):
        """
        Calls the repository update for IID 42 with a disallowed field (title) and stores the result in self.updated.
        
        Used to verify whether the repository rejects updates to disallowed fields.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.updated = await repo.update(42, title="New Title")

    def then_update_should_return_true(self):
        """
        Asserts that the repository update operation reported success.
        
        Raises:
            AssertionError: If the recorded update result is not `True`.
        """
        assert self.updated is True

    async def and_title_should_remain_unchanged(self):
        """
        Verify that the merge request's title remains "Original Title" after an update attempt that included a disallowed title change.
        
        Raises:
            AssertionError: If the merge request is not found or its title is not "Original Title"; the message includes the actual title when different.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is not None
            assert mr.title == "Original Title", f"Title should not change, got '{mr.title}'"

    async def do_cleanup(self):
        """
        Release the initialized test database context and clean up its resources.
        
        This exits the asynchronous database context manager created for the scenario, ensuring connections and temporary state are closed and cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
