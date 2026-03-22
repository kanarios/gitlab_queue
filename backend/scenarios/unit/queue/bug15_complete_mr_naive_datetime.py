"""BUG-15: complete_mr should handle naive datetimes without TypeError."""

from __future__ import annotations

from datetime import datetime

import vedro

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.queue_item import QueueItem
from scenarios.fakes import FakeDatabase, FakeResult, FakeSession


class Scenario(vedro.Scenario):
    subject = "complete_mr handles naive datetime without TypeError"

    def given_queue_manager_with_naive_datetime_item(self):
        # Create a QueueItem with NAIVE datetimes (no tzinfo)
        naive_queued_at = datetime(2025, 1, 1, 12, 0, 0)  # no tzinfo
        naive_started_at = datetime(2025, 1, 1, 12, 5, 0)  # no tzinfo

        self.queue_item = QueueItem(
            mr_iid=42,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="merging",
            queued_at=naive_queued_at,
            started_at=naive_started_at,
        )

        # Fake session for transaction (execute is a no-op)
        tx_session = FakeSession()

        # Fake session for get_queue_item — returns row data
        row_data = {
            "iid": 42,
            "title": "Test MR",
            "author_name": "Test",
            "author_username": "test",
            "author_avatar": None,
            "status": "merging",
            "is_hotfix": 0,
            "labels": "[]",
            "target_branch": "main",
            "queued_at": naive_queued_at.isoformat(),
            "started_at": naive_started_at.isoformat(),
            "finished_at": None,
            "pipeline_id": None,
            "pipeline_status": None,
            "expected_sha": None,
            "retry_count": 0,
            "last_error": None,
            "stale_warning_sent": 0,
        }

        async def session_execute(sql, params=None):
            return FakeResult(_row_data=row_data)

        read_session = FakeSession(execute_fn=session_execute)

        self.db = FakeDatabase(
            _transaction_sessions=[tx_session],
            _session_sessions=[read_session],
        )
        self.qm = QueueManager(db=self.db)

    async def when_complete_mr_is_called(self):
        self.error = None
        try:
            await self.qm.complete_mr(99999, 42, status="merged")
        except TypeError as e:
            self.error = e

    def then_no_type_error_should_occur(self):
        assert self.error is None, f"complete_mr raised TypeError with naive datetime: {self.error}"
