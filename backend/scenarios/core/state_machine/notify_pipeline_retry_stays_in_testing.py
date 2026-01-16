"""Test notify_pipeline_retry stays in testing and calls notifier."""

import vedro
from scenarios.library import QueueState
from scenarios.contexts.state_machine_helpers import (
    create_mock_notifier,
    create_mock_queue_manager,
    create_state_machine,
)


class Scenario(vedro.Scenario):
    subject = "notify_pipeline_retry stays in testing and calls notifier"

    async def given_state_machine_in_testing(self):
        self.notifier = create_mock_notifier()
        self.queue_manager = create_mock_queue_manager()
        self.sm = await create_state_machine(
            self.notifier,
            self.queue_manager,
            mr_iid=123,
            start_value=QueueState.TESTING,
        )

    async def when_notify_pipeline_retry_is_called(self):
        await self.sm.notify_pipeline_retry(
            old_pipeline_id=100,
            old_pipeline_url="https://gitlab.com/pipeline/100",
            new_pipeline_id=200,
            new_pipeline_url="https://gitlab.com/pipeline/200",
            retry_count=1,
            max_retries=2,
            failed_jobs=["test"],
        )

    def then_it_should_stay_in_testing_state(self):
        assert self.sm.current_state.id == "testing"

    def and_notifier_should_be_called_with_pipeline_retry_template(self):
        self.notifier.notify.assert_called()
        call_args = self.notifier.notify.call_args
        assert call_args[0][0] == 123  # mr_iid
        assert call_args[0][1] == "pipeline_retry"  # template
