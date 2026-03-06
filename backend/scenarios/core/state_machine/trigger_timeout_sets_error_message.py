"""BUG 4: trigger_timeout should set error_message for history."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "trigger_timeout sets error_message in failure_reason for history"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_timeout_is_triggered(self):
        await self.sm.trigger_timeout(max_wait_hours=4)

    def then_complete_mr_failure_reason_should_not_be_none(self):
        assert len(self.queue_manager.complete_calls) >= 1
        call = self.queue_manager.complete_calls[-1]
        assert call.get("failure_reason") is not None, "Expected failure_reason to be set, got None"

    def and_failure_reason_should_contain_timeout_info(self):
        call = self.queue_manager.complete_calls[-1]
        reason = call["failure_reason"]
        assert "4" in reason, f"Expected hours in failure_reason, got '{reason}'"
