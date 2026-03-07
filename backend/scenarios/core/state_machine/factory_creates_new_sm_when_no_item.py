"""Test create_state_machine_for_mr creates new SM when no queue item."""

import vedro
from scenarios.contexts.state_machine_helpers import create_mock_notifier
from scenarios.fakes import FakeQueueManager

from gitlab_queue.core.state_machine import create_state_machine_for_mr


class Scenario(vedro.Scenario):
    subject = "create_state_machine_for_mr creates new sm when no queue item"

    def given_queue_manager_with_no_item(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = FakeQueueManager()

    async def when_factory_is_called(self):
        self.sm = await create_state_machine_for_mr(
            mr_iid=42,
            notifier=self.notifier,
            queue_manager=self.queue_manager,
            target_branch="main",
        )

    def then_it_should_be_in_queued_state(self):
        assert self.sm.current_state.id == "queued"

    def and_it_should_have_correct_target_branch(self):
        assert self.sm.target_branch == "main"
