"""Test concurrent moves of one retry item create a single DLQ entry."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import vedro
from sqlalchemy import text

from gitlab_queue.db.database import Database
from gitlab_queue.webhooks.retry_manager import RetryItemNotFoundError, WebhookRetryManager

from ._helpers import create_test_payload


class Scenario(vedro.Scenario):
    subject = "concurrent DLQ moves insert one entry and report a stale caller"

    async def given_retry_item_and_database(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp_dir.name) / "retry.db"
        self.db = Database(database_url=f"sqlite+aiosqlite:///{db_path}")
        await self.db.initialize()
        self.manager = WebhookRetryManager(db=self.db, base_delay_seconds=0)
        await self.manager.ensure_schema()
        self.retry_id = await self.manager.add_to_retry_queue(
            "merge_request",
            create_test_payload(),
            "initial failure",
            project_id=303,
        )
        async with self.db.session() as session:
            result = await session.execute(
                text("SELECT * FROM webhook_retry_queue WHERE id = :id AND project_id = :project_id"),
                {"id": self.retry_id, "project_id": 303},
            )
            self.stale_snapshot = result.mappings().one()
            await session.commit()

    async def when_both_callers_move_the_same_retry_item(self):
        self.results = await asyncio.gather(
            self.manager._move_to_dlq(self.stale_snapshot, "removed project", increment_attempt=False),
            self.manager._move_to_dlq(self.stale_snapshot, "removed project", increment_attempt=False),
            return_exceptions=True,
        )
        self.dlq_entries = await self.manager.get_dlq_entries(project_id=303)
        self.remaining_retries = await self.manager.get_events_ready_for_retry(project_id=303)

    def then_only_one_move_succeeds_and_the_other_reports_not_found(self):
        assert sum(isinstance(result, int) for result in self.results) == 1
        assert sum(isinstance(result, RetryItemNotFoundError) for result in self.results) == 1
        assert all(isinstance(result, int | RetryItemNotFoundError) for result in self.results)

    def and_exactly_one_dlq_entry_exists_with_no_retry_source(self):
        assert len(self.dlq_entries) == 1
        successful_dlq_ids = [result for result in self.results if isinstance(result, int)]
        assert successful_dlq_ids == [self.dlq_entries[0].id]
        assert self.dlq_entries[0].project_id == 303
        assert self.dlq_entries[0].attempt_count == 0
        assert self.remaining_retries == []

    async def do_cleanup(self):
        await self.db.close()
        self._tmp_dir.cleanup()
