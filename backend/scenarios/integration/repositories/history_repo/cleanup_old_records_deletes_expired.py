"""Test that cleanup_old_records deletes expired history records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import vedro
from scenarios.contexts.sqlite_client import initialized_test_database
from scenarios.integration.repositories._helpers import create_tables, seed_history

from gitlab_queue.db.repositories import HistoryRepository


class Scenario(vedro.Scenario):
    subject = "cleanup_old_records deletes expired history records"

    async def given_database_with_old_and_recent_history(self):
        self._db_ctx = initialized_test_database()
        self.db = await self._db_ctx.__aenter__()
        await create_tables(self.db)

        now = datetime.now(UTC)
        async with self.db.transaction() as session:
            await seed_history(
                session,
                iid=1,
                finished_at=(now - timedelta(days=400)).isoformat(),
            )
            await seed_history(
                session,
                iid=2,
                finished_at=now.isoformat(),
            )

    async def when_cleanup_old_records_is_called(self):
        async with self.db.transaction() as session:
            repo = HistoryRepository(session)
            self.deleted_count = await repo.cleanup_old_records(retention_days=1)

    def then_one_record_should_be_deleted(self):
        assert self.deleted_count == 1

    async def and_recent_record_should_remain(self):
        async with self.db.session() as session:
            repo = HistoryRepository(session)
            result = await repo.get_history()
            assert result.total == 1
            assert result.items[0].iid == 2

    async def do_cleanup(self):
        await self._db_ctx.__aexit__(None, None, None)
