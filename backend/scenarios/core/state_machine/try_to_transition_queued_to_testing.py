"""Test queued state cannot directly transition to testing."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from statemachine.exceptions import TransitionNotAllowed


class Scenario(vedro.Scenario):
    subject = "try to transition queued directly to testing"

    async def given_state_machine_in_queued(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
        )

    async def when_rebase_complete_is_triggered(self):
        self.exception = None
        try:
            await self.sm.trigger_rebase_complete(
                pipeline_id=456,
                pipeline_url="https://gitlab.com/pipeline/456",
            )
        except TransitionNotAllowed as e:
            self.exception = e

    def then_it_should_raise_transition_not_allowed(self):
        assert self.exception is not None
        assert isinstance(self.exception, TransitionNotAllowed)
