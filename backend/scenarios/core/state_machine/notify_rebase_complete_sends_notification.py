"""Test notify_rebase_complete calls notifier with rebase_complete template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "notify_rebase_complete calls notifier with rebase_complete template"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.REBASING,
        )

    async def when_notify_rebase_complete_is_called(self):
        await self.sm.notify_rebase_complete()

    def then_it_should_stay_in_rebasing_state(self):
        assert self.sm.current_state.id == "rebasing"

    def and_notifier_should_be_called_with_rebase_complete_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "rebase_complete"  # template
