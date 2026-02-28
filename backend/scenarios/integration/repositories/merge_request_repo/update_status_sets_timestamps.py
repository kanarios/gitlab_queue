"""Test that update_status sets timestamps automatically."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "update_status sets started_at timestamp automatically"

    async def given_database_with_queued_mr(self):
        """
        Prepare a test database and seed it with a merge request in "queued" status.

        Creates an initialized test database context, creates required tables, seeds a merge request with iid 42 and status "queued", and stores the database context and handle on self._db_ctx and self.db for later steps and cleanup.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42, status="queued")

    async def when_status_is_updated_to_rebasing(self):
        """
        Updates the merge request with iid 42 to status "rebasing" and records whether the update succeeded.

        This method performs the repository update and stores the resulting boolean in self.updated.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.updated = await repo.update_status(42, "rebasing")

    def then_update_should_succeed(self):
        """
        Verify that the repository update operation reported success.

        Raises:
            AssertionError: If the update did not succeed (i.e., `self.updated` is not `True`).
        """
        assert self.updated is True

    async def and_started_at_should_be_set(self):
        """
        Asserts that the merge request with iid 42 has status "rebasing" and a non-null started_at timestamp.

        Opens a database session, retrieves the merge request by iid, and verifies it exists, its status equals "rebasing", and its started_at field is set.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            mr = await repo.get_by_iid(42)
            assert mr is not None
            assert mr.status == "rebasing"
            assert mr.started_at is not None

    async def do_cleanup(self):
        """
        Exit and clean up the test database context used by the scenario.

        Closes the asynchronous database context manager to release connections and other related resources.
        """
        await self._db_ctx.__aexit__(None, None, None)
