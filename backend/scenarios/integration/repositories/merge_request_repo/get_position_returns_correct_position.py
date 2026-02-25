"""Test that get_position returns the correct 1-indexed position."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_position returns correct 1-indexed position"

    async def given_database_with_ordered_mrs(self):
        """
        Set up an in-memory test database, create required tables, and seed three queued merge requests with ordered queued_at timestamps.
        
        Initializes self._db_ctx and self.db, creates database tables, and inserts three merge requests:
        - iid=1 queued at now minus 30 minutes
        - iid=2 queued at now minus 20 minutes
        - iid=3 queued at now minus 10 minutes
        
        The seeded `queued_at` values are stored as ISO-formatted timestamps.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=1,
                status="queued",
                queued_at=(now - timedelta(minutes=30)).isoformat(),
            )
            await seed_mr(
                session,
                iid=2,
                status="queued",
                queued_at=(now - timedelta(minutes=20)).isoformat(),
            )
            await seed_mr(
                session,
                iid=3,
                status="queued",
                queued_at=(now - timedelta(minutes=10)).isoformat(),
            )

    async def when_get_position_is_called_for_second_mr(self):
        """
        Invoke MergeRequestRepository.get_position for the merge request with iid 2 and store the returned 1-indexed position on self.position.
        
        This step opens a database session, constructs the repository, calls get_position(2), and assigns the result to self.position.
        """
        async with self.db.session() as session:
            repo = MergeRequestRepository(session)
            self.position = await repo.get_position(2)

    def then_position_should_be_2(self):
        """
        Asserts that the retrieved merge request position equals 2.
        """
        assert self.position == 2

    async def do_cleanup(self):
        """
        Exit the test database context and release its resources.
        
        Exits the underlying asynchronous context manager for the test database, ensuring connections, transactions, and other resources are properly closed.
        """
        await self._db_ctx.__aexit__(None, None, None)
