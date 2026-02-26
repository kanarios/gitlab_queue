"""Test that get_history filters by date range."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_history filters by date range"

    async def given_database_with_dated_history(self):
        """
        Prepare a test database and seed it with three history records having distinct finished_at timestamps.

        Sets up an initialized test database context, creates required tables, stores the database handle on the instance, records today's date as `self.today`, and inserts three history entries:
        - iid=1 with finished_at set to now
        - iid=2 with finished_at 3 days before now
        - iid=3 with finished_at 10 days before now
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        self.today = now.date()

        async with self.db.transaction() as session:
            await seed_history(
                session,
                iid=1,
                finished_at=now.isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                finished_at=(now - timedelta(days=3)).isoformat(),
            )
            await seed_history(
                session,
                iid=3,
                finished_at=(now - timedelta(days=10)).isoformat(),
            )

    async def when_get_history_is_called_with_date_range(self):
        """
        Fetch history records for the date range from self.today - 5 days to self.today and store the fetched result on self.result.

        Opens a database session, constructs a HistoryRepository, and assigns the repository's get_history result to self.result.
        """
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = HistoryRepository(session)
        self.result = await repo.get_history(
            date_from=self.today - timedelta(days=5),
            date_to=self.today,
        )

    def then_only_records_within_range_should_be_returned(self):
        """
        Asserts that the repository result contains exactly the two history records within the expected date range.

        Verifies that `self.result.total` equals 2 and that the set of `iid` values in `self.result.items` is exactly {1, 2}; raises AssertionError if these conditions are not met.
        """
        assert self.result.total == 2
        iids = {item.iid for item in self.result.items}
        assert iids == {1, 2}

    async def do_cleanup(self):
        """
        Tears down the scenario's database and session async contexts.

        Exits the active session and database context managers to release resources opened during the scenario setup.
        """
        await self._session_ctx.__aexit__(None, None, None)
        await self._db_ctx.__aexit__(None, None, None)
