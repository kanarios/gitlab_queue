from __future__ import annotations

from datetime import UTC, datetime

import vedro

from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.models.queue_item import QueueItem
from scenarios.fakes import FakeNotifier, FakeQueueManager


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

        self.notifier = FakeNotifier()

        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

    async def when_state_machine_is_created_for_existing_item(self):
        await create_state_machine_for_mr(
            project_id=99999,
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch="main",
        )

    def then_notifier_is_not_called(self):
        assert len(self.notifier.notify_calls) == 0
