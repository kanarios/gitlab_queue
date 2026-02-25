"""Test that get_history returns paginated results."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_history returns paginated results"

    async def given_database_with_history_records(self):
        """
        Set up a test database context, create required tables, and seed five history records.
        
        Creates an async test database context and tables, then inserts five history entries with iids 100 through 104. Each record's `finished_at` is set to the current UTC time minus 0..4 minutes respectively.
        """
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            for i in range(5):
                await seed_history(
                    session,
                    iid=100 + i,
                    finished_at=(now - timedelta(minutes=i)).isoformat(),
                )

    async def when_get_history_is_called_with_pagination(self):
        """
        Call HistoryRepository.get_history for page 1 with 2 items per page and store the paginated result on self.result.
        
        Sets self.result to the pagination object returned by the repository.
        """
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            self.result = await repo.get_history(page=1, per_page=2)

    def then_result_should_have_2_items(self):
        """
        Assert that the paginated result contains exactly two items.
        
        Raises:
            AssertionError: If the number of items in self.result.items is not 2.
        """
        assert len(self.result.items) == 2

    def and_total_should_be_5(self):
        """
        Assert that the paginated result reports a total of 5 items.
        """
        assert self.result.total == 5

    def and_total_pages_should_be_3(self):
        """
        Verify that the paginated result reports three total pages.
        
        Raises:
            AssertionError: If the result's `total_pages` is not equal to 3.
        """
        assert self.result.total_pages == 3

    def and_page_should_be_1(self):
        """
        Asserts that the query result's page is 1.
        
        Raises:
            AssertionError: If the result's page is not 1.
        """
        assert self.result.page == 1

    async def do_cleanup(self):
        """
        Exit the test database context and release associated resources used by the scenario.
        """
        await self._db_ctx.__aexit__(None, None, None)
