"""BUG-15: complete_mr should handle naive datetimes without TypeError."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.queue import QueueManager
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "complete_mr handles naive datetime without TypeError"

    def given_queue_manager_with_naive_datetime_item(self):
        self.db = MagicMock()
        self.qm = QueueManager(db=self.db)

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

        # Mock get_queue_item to return item with naive datetimes
        self.qm.get_queue_item = AsyncMock(return_value=self.queue_item)

        # Mock db.transaction as async context manager
        self.session_mock = AsyncMock()
        self.session_mock.execute = AsyncMock()

        class AsyncCtxManager:
            async def __aenter__(self_inner):
                return self.session_mock

            async def __aexit__(self_inner, *args):
                pass

        self.db.transaction = lambda: AsyncCtxManager()

    async def when_complete_mr_is_called(self):
        self.error = None
        try:
            await self.qm.complete_mr(42, status="merged")
        except TypeError as e:
            self.error = e

    def then_no_type_error_should_occur(self):
        assert self.error is None, f"complete_mr raised TypeError with naive datetime: {self.error}"
