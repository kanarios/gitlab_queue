"""Test _sync_missing_mrs_from_gitlab adds MR not in queue.

When list_mrs_with_label returns an MR that is not in the active queue,
the sync method should call add_to_queue to add the missing MR so it
gets processed.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
)


class Scenario(vedro.Scenario):
    subject = "sync missing mrs from gitlab adds mr not in queue"

    def given_processor_with_mr_in_gitlab_but_not_in_queue(self):
        """MR есть в GitLab, но отсутствует в очереди."""
        self.processor = create_mock_processor()

        self.mock_mr = create_mock_mr(
            iid=99,
            state="opened",
            labels=["merge_queue"],
        )

        self.processor.gitlab_client.listed_mrs = [self.mock_mr]

        # Active queue is empty - MR is not in the queue (default for FakeQueueManager)

    async def when_sync_missing_mrs_from_gitlab_is_called(self):
        """Запускаем синхронизацию отсутствующих MR из GitLab."""
        await self.processor._sync_missing_mrs_from_gitlab()

    def then_add_to_queue_is_called_with_the_mr(self):
        """Проверяем, что MR добавили в очередь."""
        assert len(self.processor.queue_manager.add_to_queue_calls) == 1
        call = self.processor.queue_manager.add_to_queue_calls[0]
        assert call["mr"] == self.mock_mr
        assert call["is_hotfix"] is False
