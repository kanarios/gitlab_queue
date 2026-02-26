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
        call_args = self.notifier.notify.call_args
        template = call_args[0][1]
        assert template == "generic_failure", f"Expected 'generic_failure' template, got '{template}'"

    def and_notify_should_not_have_pipeline_id_zero(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("pipeline_id") != 0, "generic_failure should not have pipeline_id=0"

    def and_notify_should_not_have_hash_url(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("pipeline_url") != "#", "generic_failure should not have pipeline_url='#'"
