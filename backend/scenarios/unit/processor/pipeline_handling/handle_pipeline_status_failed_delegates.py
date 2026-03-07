"""Test handle_pipeline_status delegates to handle_pipeline_failure when status is failed.

When pipeline.status == "failed", handle_pipeline_status should call
handle_pipeline_failure and return its result.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "handle_pipeline_status delegates to handle_pipeline_failure for failed status"

    def given_processor_with_failed_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=0))

        queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.add_item(queue_item)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        # Pipeline has a failed job; with job_retry_count=0, it will be exhausted immediately
        self.failed_job = create_job(id=10, name="unit_tests", status="failed")
        self.processor.gitlab_client.pipeline_jobs_response = [self.failed_job]

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.processor._pipeline_handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_pipeline_failed_was_triggered_with_exhausted_job(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == [self.failed_job.name]
        assert call["retried_jobs"] == {}
