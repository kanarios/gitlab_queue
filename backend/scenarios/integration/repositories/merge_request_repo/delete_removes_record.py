"""Test that delete removes an MR record from the database."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "delete removes merge request record"

    async def given_database_with_mr(self):
        """
        Prepare a temporary test database with required tables and a seeded merge request record (iid 42).

        Sets self._db_ctx to the test database context manager and self.db to the entered database session, creates the schema, and seeds a merge request with iid 42 for use by subsequent test steps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=42)

    async def when_mr_is_deleted(self):
        """
        Deletes the merge request with iid 42 and records whether the deletion succeeded.

        Sets self.deleted to `True` if the repository reported the record was removed, `False` otherwise.
        """
        async with self.db.transaction() as session:
            repo = MergeRequestRepository(session)
            self.deleted = await repo.delete(42)

    def then_delete_should_succeed(self):
        """
        Asserts that the prior delete operation reported success.

        Raises:
            AssertionError: If the delete operation did not return True.
        """
        assert self.deleted is True

    async def and_mr_should_not_be_in_database(self):
        """
        Verifies that the merge request with iid 42 is not present in the database.

        Queries the MergeRequestRepository for iid 42 and asserts the lookup returns `None`.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            result = await repo.get_by_iid(42)
            assert result is None

    async def do_cleanup(self):
        """
        Exit the test database asynchronous context and release associated resources.

        Closes the in-memory/temporary database context created for the scenario so connections and transactions are cleaned up.
        """
        await self._db_ctx.__aexit__(None, None, None)
