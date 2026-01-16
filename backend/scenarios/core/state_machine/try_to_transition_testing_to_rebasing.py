"""Test testing state cannot transition back to rebasing."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from statemachine.exceptions import TransitionNotAllowed


class Scenario(vedro.Scenario):
    subject = "try to transition testing back to rebasing"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_start_processing_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_start_processing()
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)
