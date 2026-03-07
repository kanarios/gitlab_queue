"""Test: _handle_pipeline_failure syncs retried_jobs with DB to prevent double retry."""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import MergeProcessor
from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import (
    FakeCurrentState,
    FakeGitLabClient,
    FakeNotifier,
    FakeQueueManager,
    FakeSettings,
    FakeStateMachine,
    create_job,
)

from ._helpers import (
    create_mock_pipeline,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "processor uses DB retried_jobs when it is higher than local value"

    def given_processor_with_db_retried_jobs_ahead(self):
        # DB already has test_job retried once (webhook handler did it)
        self.queue_item = create_test_queue_item(mr_iid=42, state="testing", retried_jobs={"test_job": 1})
        self.queue_manager = FakeQueueManager()
        self.queue_manager.add_item(self.queue_item)

        gitlab_client = FakeGitLabClient()
        # Pipeline has a failed job that was already retried once in DB
        gitlab_client.pipeline_jobs_response = [
            create_job(id=1, name="test_job", status="failed"),
        ]

        # job_retry_count=1 so that DB retried_jobs={"test_job": 1} >= 1 triggers exhausted path
        self.processor = MergeProcessor(
            gitlab_client=gitlab_client,
            queue_manager=self.queue_manager,
            notifier=FakeNotifier(),
            settings=FakeSettings(job_retry_count=1),
        )

        self.sm = FakeStateMachine(current_state=FakeCurrentState(id="testing"))
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        self.pipeline = create_mock_pipeline(status="failed")

    async def when_handle_pipeline_failure_is_called(self):
        # Local retried_jobs is empty, but DB has test_job=1
        self.result = await self.processor._handle_pipeline_failure(
            self.ctx,
            self.pipeline,
            retried_jobs={},
        )

    def then_result_should_be_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_retried_jobs_should_reflect_db_value(self):
        # DB has test_job=1, so trigger_pipeline_failed should use that
        assert len(self.sm.pipeline_failed_calls) == 1
        retried = self.sm.pipeline_failed_calls[0].get("retried_jobs", {})
        assert retried.get("test_job", 0) == 1
