"""Test that get_stale_mrs returns only unwarned stale MRs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_stale_mrs returns only unwarned stale merge requests"

    async def given_database_with_stale_mrs(self):
        """
        Prepare a test database containing two stale merge requests: one with stale_warning_sent = 0 and one with stale_warning_sent = 1.

        Creates a test database context and session, ensures database tables exist, computes a queued_at timestamp two hours in the past (ISO format), and inserts two merge requests:
        - iid=1, status "queued", queued_at=<old_time>, stale_warning_sent=0
        - iid=2, status "queued", queued_at=<old_time>, stale_warning_sent=1

        Sets self._db_ctx to the test database context and self.db to the opened database session for later use.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()

        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=1,
                status="queued",
                queued_at=old_time,
                stale_warning_sent=0,
            )
            await seed_mr(
                session,
                iid=2,
                status="queued",
                queued_at=old_time,
                stale_warning_sent=1,
            )

    async def when_get_stale_mrs_is_called(self):
        """
        Retrieve merge requests queued longer than 1 hour via get_stale_mrs(1).
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_stale_mrs(1)

    def then_only_unwarned_stale_mr_should_be_returned(self):
        """
        Assert that the repository returned exactly one stale merge request and that it is the unwarned MR.

        Verifies that:
        - exactly one merge request is present in self.result,
        - that merge request has iid equal to 1,
        - and its stale_warning_sent flag equals 0.
        """
        assert len(self.result) == 1
        assert self.result[0].iid == 1
        assert self.result[0].stale_warning_sent == 0

    async def do_cleanup(self):
        """
        Close the database session and test database context.

        Asynchronously exit the scenario's session and database context managers to release resources opened during setup.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
