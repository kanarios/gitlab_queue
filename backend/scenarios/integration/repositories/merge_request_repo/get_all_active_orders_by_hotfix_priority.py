"""Test that get_all_active orders by hotfix priority then queued_at."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_mr

from gitlab_queue.db.repositories import MergeRequestRepository


class Scenario(vedro.Scenario):
    subject = "get_all_active orders by hotfix priority then queued_at"

    async def given_database_with_mixed_mrs(self):
        """
        Set up an in-memory test database and seed it with three merge requests (one hotfix and two regular) for the scenario.

        Seeds three MRs inside an asynchronous transaction:
        - iid=1: regular MR queued 10 minutes before now
        - iid=2: hotfix MR queued at now
        - iid=3: regular MR queued 5 minutes before now

        The created database context and connection are stored on the instance for later use.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_mr(
                session,
                iid=1,
                title="Regular MR 1",
                is_hotfix=0,
                queued_at=(now - timedelta(minutes=10)).isoformat(),
            )
            await seed_mr(
                session,
                iid=2,
                title="Hotfix MR",
                is_hotfix=1,
                queued_at=now.isoformat(),
            )
            await seed_mr(
                session,
                iid=3,
                title="Regular MR 2",
                is_hotfix=0,
                queued_at=(now - timedelta(minutes=5)).isoformat(),
            )

    async def when_get_all_active_is_called(self):
        """
        Fetch all active merge requests via the repository and store the returned list on the scenario.

        This method obtains an asynchronous session from the test database (saved to self._session_ctx for later cleanup), constructs a MergeRequestRepository using that session, and assigns the repository's get_all_active() result to self.result.
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = MergeRequestRepository(session)
        self.result = await repo.get_all_active()

    def then_hotfix_should_be_first(self):
        assert len(self.result) == 3
        assert self.result[0].iid == 2, "Hotfix should be first"
        assert self.result[0].is_hotfix == 1

    def and_regular_mrs_should_follow_in_queued_at_order(self):
        """
        Asserts that non-hotfix merge requests appear after hotfixes ordered by their queued_at time.

        Verifies the second result has iid 1 (the older regular MR) and the third result has iid 3 (the newer regular MR).
        """
        assert self.result[1].iid == 1, "Older regular MR should be second"
        assert self.result[2].iid == 3, "Newer regular MR should be third"

    async def do_cleanup(self):
        """
        Release the scenario's asynchronous session and database contexts.

        Await exiting the session and database context managers opened during the scenario to close connections and free resources.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
