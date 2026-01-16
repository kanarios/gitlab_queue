"""Test creating state machine with custom target branch."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "create state machine with custom target branch"

    def given_dependencies(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()

    async def when_state_machine_is_created_with_target_branch(self):
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            target_branch="main",
        )

    def then_it_should_have_correct_target_branch(self):
        assert self.sm.target_branch == "main"
