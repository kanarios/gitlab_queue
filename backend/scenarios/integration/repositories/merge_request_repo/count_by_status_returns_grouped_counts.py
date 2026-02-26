"""Test that count_by_status returns correct grouped counts."""

from __future__ import annotations

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "count_by_status returns grouped counts for active states"

    async def given_database_with_various_statuses(self):
        """
        Set up a test database and seed it with merge requests in several statuses.

        Creates the necessary schema and inserts five merge requests: two with status "queued",
        one "rebasing", one "testing", and one "merged", leaving the test database ready for
        counting/grouping assertions.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        async with self.db.transaction() as session:
            await seed_mr(session, iid=1, status="queued")
            await seed_mr(session, iid=2, status="queued")
            await seed_mr(session, iid=3, status="rebasing")
            await seed_mr(session, iid=4, status="testing")
            await seed_mr(session, iid=5, status="merged")

    async def when_count_by_status_is_called(self):
        """
        Calls MergeRequestRepository.count_by_status and stores the resulting mapping of status names to counts on self.counts.

        Opens a database session, constructs a MergeRequestRepository with that session, awaits count_by_status(), and assigns the returned dict to self.counts.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.counts = await repo.count_by_status()

    def then_counts_should_reflect_active_statuses(self):
        """
        Assert that the repository returned counts for active statuses: "queued" equals 2, "rebasing" equals 1, and "testing" equals 1, and that "merging" is not present (treated as zero).

        Raises:
            AssertionError: if any of the expected counts do not match or if "merging" has a non-zero value.
        """
        assert self.counts["queued"] == 2
        assert self.counts["rebasing"] == 1
        assert self.counts["testing"] == 1
        assert self.counts.get("merging", 0) == 0

    def and_terminal_statuses_should_not_be_included(self):
        """
        Asserts that the terminal status "merged" is not present in the computed counts.

        Raises:
            AssertionError: If "merged" exists as a key in self.counts.
        """
        assert "merged" not in self.counts

    async def do_cleanup(self):
        """
        Exit the test database context and release associated resources.

        This performs cleanup by closing the database context manager used for the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
