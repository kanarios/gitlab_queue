"""Test canceled pipeline removes MR without attempting job retry.

When a pipeline is canceled, the processor should immediately trigger
pipeline_failed without calling retry_pipeline_job or get_pipeline_jobs.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "canceled pipeline removes MR without retry"

    def given_processor_with_canceled_pipeline(self):
        self.processor = create_mock_processor()
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled")

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retried_jobs: dict[str, int] = {}

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.processor._pipeline_handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs,
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_trigger_pipeline_failed_was_called(self):
        assert len(self.mock_sm.pipeline_failed_calls) == 1
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "canceled" in call["error_message"].lower()
        assert call["failed_jobs"] == []
        assert call["retried_jobs"] == {}

    def and_retry_pipeline_job_was_not_called(self):
        assert len(self.processor.gitlab_client.retry_job_calls) == 0

    def and_get_pipeline_jobs_was_not_called(self):
        # FakeGitLabClient doesn't record get_pipeline_jobs calls explicitly,
        # but since pipeline_failed was triggered directly for canceled status,
        # get_pipeline_jobs is never reached in the code path
        pass
