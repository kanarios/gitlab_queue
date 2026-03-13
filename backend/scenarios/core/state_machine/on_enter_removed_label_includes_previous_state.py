"""Test on_enter_removed includes correct previous_state in notify for each source state."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState
from vedro import params


class Scenario(vedro.Scenario):
    subject = "on_enter_removed from {start_state} includes previous_state={start_state}"

    @params(QueueState.QUEUED)
    @params(QueueState.REBASING)
    @params(QueueState.TESTING)
    @params(QueueState.MERGING)
    def __init__(self, start_state: str) -> None:
        self.start_state = start_state

    async def given_state_machine_in_given_state(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=self.start_state,
        )

    async def when_mark_removed_is_triggered(self):
        await self.sm.trigger_mark_removed(reason="label_removed")

    def then_notifier_should_include_correct_previous_state(self):
        call_args = self.notifier.notify_calls[0]
        assert call_args["status"] == "removed_label"
        assert call_args["previous_state"] == self.start_state
