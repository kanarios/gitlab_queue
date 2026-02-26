"""Test that get_stats_for_period returns aggregate statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_stats_for_period returns aggregate statistics"

    async def given_database_with_varied_history(self):
        """
        Prepare a test database populated with three history records having varied statuses and metrics.

        Initializes a test database context (stored on self._db_ctx and self.db), creates required tables, records the current date in self.today, and inserts three history rows:
        - iid=1: status "merged", is_hotfix=1, wait_time_seconds=60, processing_time_seconds=120
        - iid=2: status "failed", wait_time_seconds=30, processing_time_seconds=90
        - iid=3: status "conflict"

        The inserted records use the current UTC timestamp as their finished_at value.
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
                status="merged",
                is_hotfix=1,
                wait_time_seconds=60,
                processing_time_seconds=120,
                finished_at=now.isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                status="failed",
                wait_time_seconds=30,
                processing_time_seconds=90,
                finished_at=now.isoformat(),
            )
            await seed_history(
                session,
                iid=3,
                status="conflict",
                finished_at=now.isoformat(),
            )

    async def when_get_stats_for_period_is_called(self):
        """
        Fetch aggregate history statistics for the 24-hour period ending at self.today and store the result on the scenario.

        Calls HistoryRepository.get_stats_for_period with (self.today - 1 day, self.today) and assigns the returned statistics object to `self.stats`.
        """
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            self.stats = await repo.get_stats_for_period(
                self.today - timedelta(days=1),
                self.today,
            )

    def then_total_processed_should_be_3(self):
        """
        Verify that the aggregated total_processed equals 3.

        Raises:
            AssertionError: if `self.stats.total_processed` is not 3.
        """
        assert self.stats.total_processed == 3

    def and_success_count_should_be_1(self):
        assert self.stats.success_count == 1

    def and_failed_count_should_be_1(self):
        """
        Asserts that the retrieved stats report exactly one failed item.

        Raises:
                AssertionError: If `self.stats.failed_count` is not equal to 1.
        """
        assert self.stats.failed_count == 1

    def and_conflict_count_should_be_1(self):
        """
        Asserts that the collected statistics report exactly one conflict record.

        Raises an AssertionError if `self.stats.conflict_count` is not equal to 1.
        """
        assert self.stats.conflict_count == 1

    def and_hotfix_count_should_be_1(self):
        """
        Asserts that the collected statistics report exactly one hotfix.

        Raises:
            AssertionError: If `self.stats.hotfix_count` is not 1.
        """
        assert self.stats.hotfix_count == 1

    async def do_cleanup(self):
        """
        Tears down the test database context used by the scenario.

        Closes and cleans up resources associated with the initialized test database.
        """
        await self._db_ctx.__aexit__(None, None, None)
