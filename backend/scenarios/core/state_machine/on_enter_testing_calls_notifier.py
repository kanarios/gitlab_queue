"""Test on_enter_testing calls notifier with pipeline info."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_testing calls notifier with pipeline info"

    async def given_state_machine_in_rebasing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.REBASING,
        )

    async def when_rebase_complete_is_triggered(self):
        """
        Simulates a completed rebase event by triggering the state machine with pipeline details.
        
        Triggers the state's rebase completion event using pipeline_id 456 and pipeline_url "https://gitlab.com/pipeline/456" so subsequent behavior (e.g., notifier calls) can be asserted.
        """
        await self.sm.trigger_rebase_complete(
            pipeline_id=456,
            pipeline_url="https://gitlab.com/pipeline/456",
        )

    def then_notifier_should_be_called_with_testing_template(self):
        """
        Assert that the notifier coroutine was awaited and invoked with the expected merge request IID and the "testing" template.
        
        Checks that notify() was awaited, then verifies the first positional argument equals 123 (mr_iid) and the second positional argument equals "testing" (template).
        """
        self.notifier.notify.assert_awaited()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "testing"  # template

    def and_notify_should_include_pipeline_info(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("pipeline_id") == 456
        assert call_kwargs.get("pipeline_url") == "https://gitlab.com/pipeline/456"
