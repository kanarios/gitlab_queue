"""Test create_state_machine_for_mr resumes from existing state."""

from datetime import UTC, datetime

import vedro
from scenarios.contexts.state_machine_helpers import create_mock_notifier
from scenarios.fakes import FakeQueueManager
from scenarios.library import QueueState

from gitlab_queue.core.state_machine import create_state_machine_for_mr
from gitlab_queue.models.queue_item import QueueItem


class Scenario(vedro.Scenario):
    subject = "create_state_machine_for_mr resumes from existing state"

    def given_queue_manager_with_existing_item_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(
            QueueItem(
                mr_iid=42,
                title="Existing MR",
                author_name="Test",
                author_username="test",
                target_branch="master",
                state=QueueState.TESTING,
                queued_at=datetime.now(UTC),
            )
        )

    async def when_factory_is_called(self):
        self.sm = await create_state_machine_for_mr(
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
        )

    def then_it_should_be_in_testing_state(self):
        assert self.sm.current_state.id == "testing"
