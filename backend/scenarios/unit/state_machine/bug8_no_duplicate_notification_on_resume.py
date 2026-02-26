from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "no duplicate notification on resume"

    def given_existing_queue_item_in_testing_state(self):
        self.queue_item = QueueItem(
            mr_iid=42,
            title="Test MR",
            author_name="Test",
            author_username="test",
            target_branch="main",
            state="testing",
            queued_at=datetime.now(UTC),
        )

        self.notifier = MagicMock()
        self.notifier.notify = AsyncMock()
        self.notifier.remove_queue_label = AsyncMock()

        self.queue_manager = MagicMock()
        self.queue_manager.get_queue_item = AsyncMock(return_value=self.queue_item)
        self.queue_manager.update_mr_state = AsyncMock(return_value=True)
        self.queue_manager.complete_mr = AsyncMock(return_value=True)

    async def when_state_machine_is_created_for_existing_item(self):
        await create_state_machine_for_mr(
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch="main",
        )

    def then_notifier_is_not_called(self):
        self.notifier.notify.assert_not_awaited()
