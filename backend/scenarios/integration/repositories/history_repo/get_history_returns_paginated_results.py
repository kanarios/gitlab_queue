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
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            self.result = await repo.get_history(page=1, per_page=2)

    def then_result_should_have_2_items(self):
        assert len(self.result.items) == 2

    def and_total_should_be_5(self):
        assert self.result.total == 5

    def and_total_pages_should_be_3(self):
        assert self.result.total_pages == 3

    def and_page_should_be_1(self):
        assert self.result.page == 1

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
