"""BUG 1: trigger_rebase_failed from testing state raises TransitionNotAllowed."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState
from statemachine.exceptions import TransitionNotAllowed


class Scenario(vedro.Scenario):
    subject = "trigger_rebase_failed from testing raises TransitionNotAllowed"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_trigger_rebase_failed_is_called(self):
        self.exception = None
        try:
            await self.sm.trigger_rebase_failed(
                conflicted_files=["file.py"],
                error_message="Conflict detected",
            )
        except TransitionNotAllowed as e:
            self.exception = e

    def then_transition_not_allowed_should_be_raised(self):
        assert self.exception is not None, "Expected TransitionNotAllowed but no exception raised"
        assert isinstance(self.exception, TransitionNotAllowed)
