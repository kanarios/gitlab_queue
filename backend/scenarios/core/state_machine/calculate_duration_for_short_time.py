"""Test calculate duration for short time."""

from datetime import UTC, datetime

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState

from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "calculate duration for short time"

    async def given_state_machine(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
        )

    def when_calculating_duration_for_recent_item(self):
        now = datetime.now(UTC)
        item = QueueItem(
            mr_iid=123,
            title="Test",
            author_name="Test",
            author_username="test",
            target_branch="master",
            state=QueueState.QUEUED,
            queued_at=now,
        )
        self.duration = self.sm._calculate_duration(item)

    def then_it_should_return_seconds_format(self):
        assert "s" in self.duration
