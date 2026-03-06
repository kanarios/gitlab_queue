"""Test: _handle_pipeline_failure syncs retry_count with DB to prevent double increment."""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import MergeProcessor, ProcessingResult
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeSettings,
    FakeStateMachine,
)

from ._helpers import (
    create_mock_pipeline,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processor uses DB retry_count when it is higher than local value"

    def given_processor_with_db_retry_count_ahead(self):
        # Webhook handler already incremented retry_count to 1 in DB
        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", retry_count=1)
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

        # max_retries=1 so that DB retry_count=1 >= 1 triggers pipeline_failed path
        self.processor = MergeProcessor(
            gitlab_client=FakeGitLabClient(),
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(pipeline_retry_count=1),
        )

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        self.pipeline = create_mock_pipeline(status="failed")

    async def when_handle_pipeline_failure_is_called(self):
        # Local retry_count=0, but DB has retry_count=1
        self.result = await self.processor._handle_pipeline_failure(
            self.ctx,
            self.pipeline,
            retry_count=0,
            max_retries=1,
        )

    def then_result_should_be_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_retry_count_should_reflect_db_value(self):
        # DB has retry_count=1, so trigger_pipeline_failed receives 1 (not local 0)
        assert len(self.sm.pipeline_failed_calls) == 1
        assert self.sm.pipeline_failed_calls[0]["retry_count"] == 1
