"""Test on_enter_failed calls notifier with pipeline_failed template."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "on_enter_failed calls notifier with pipeline_failed template"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_pipeline_failed_is_triggered(self):
        await self.sm.trigger_pipeline_failed(
            failed_jobs=["test", "lint", "typecheck"],
            retry_count=2,
            error_message="Tests failed",
        )

    def then_notifier_should_be_called_with_pipeline_failed_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "pipeline_failed"  # template

    def and_notify_should_include_failed_jobs_and_retry_count(self):
        call_kwargs = self.notifier.notify.call_args[1]
        assert call_kwargs.get("failed_jobs") == ["test", "lint", "typecheck"]
        assert call_kwargs.get("retry_count") == 2
