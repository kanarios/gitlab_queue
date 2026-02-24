"""Test that get_history filters by date range."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "get_history filters by date range"

    async def given_database_with_dated_history(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        self.today = date.today()

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
        self._session_ctx = self.db.session()
        session = await self._session_ctx.__aenter__()
        repo = HistoryRepository(session)
        self.result = await repo.get_history(
            date_from=self.today - timedelta(days=5),
            date_to=self.today,
        )

    def then_only_records_within_range_should_be_returned(self):
        assert self.result.total == 2
        iids = {item.iid for item in self.result.items}
        assert iids == {1, 2}

    async def do_cleanup(self):
        if hasattr(self, "_session_ctx"):
            await self._session_ctx.__aexit__(None, None, None)
        if hasattr(self, "_db_ctx"):
            await self._db_ctx.__aexit__(None, None, None)
