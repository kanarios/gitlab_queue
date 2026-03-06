"""Test on_enter_failed calls notifier with pipeline_failed template."""

import vedro
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)
from scenarios.library import QueueState


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
        """
        Trigger the state machine's pipeline-failed event using a predefined failure payload.

        Sets failed_jobs to ["test", "lint", "typecheck"], retry_count to 2, and error_message to "Tests failed".
        """
        await self.sm.trigger_pipeline_failed(
            failed_jobs=["test", "lint", "typecheck"],
            retry_count=2,
            error_message="Tests failed",
        )

    def then_notifier_should_be_called_with_pipeline_failed_template(self):
        assert len(self.notifier.notify_calls) == 1
        call_args = self.notifier.notify_calls[0]
        assert call_args["mr_iid"] == 123
        assert call_args["status"] == "pipeline_failed"

    def and_notify_should_include_failed_jobs_and_retry_count(self):
        call_args = self.notifier.notify_calls[0]
        assert call_args.get("failed_jobs") == ["test", "lint", "typecheck"]
        assert call_args.get("retry_count") == 2
