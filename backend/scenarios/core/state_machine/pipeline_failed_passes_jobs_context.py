"""Test trigger_pipeline_failed passes job info to context."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "trigger_pipeline_failed passes job info to context"

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
            failed_jobs=["unit_test", "integration_test"],
            retry_count=3,
            error_message="Tests failed",
        )

    def then_context_should_contain_failure_reason(self):
        assert self.sm._context.get("failure_reason") == "pipeline_failed"

    def and_context_should_contain_failed_jobs(self):
        assert self.sm._context.get("failed_jobs") == ["unit_test", "integration_test"]

    def and_context_should_contain_retry_count(self):
        assert self.sm._context.get("retry_count") == 3
