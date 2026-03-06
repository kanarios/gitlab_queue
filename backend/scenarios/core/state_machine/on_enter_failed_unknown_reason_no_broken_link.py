"""BUG 5: fallback for unknown failure reason should not have broken pipeline link."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


class Scenario(vedro.Scenario):
    subject = "on_enter_failed with unknown reason uses generic_failure template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_pipeline_failed_with_unknown_reason(self):
        self.sm._context["failure_reason"] = "unknown"
        self.sm._context["error_message"] = "Something went wrong"
        await self.sm.pipeline_failed()

    def then_notifier_should_use_generic_failure_template(self):
        assert len(self.notifier.notify_calls) == 1
        call_args = self.notifier.notify_calls[-1]
        assert call_args["status"] == "generic_failure"

    def and_notify_should_only_contain_expected_keys(self):
        call_args = self.notifier.notify_calls[-1]
        assert set(call_args.keys()) == {"mr_iid", "status", "failed_at", "error_message"}
