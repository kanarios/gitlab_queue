"""Test job retry: get_pipeline_jobs API error removes MR.

When get_pipeline_jobs raises GitLabAPIError, the processor cannot
determine which jobs to retry and should trigger pipeline_failed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import (
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "job retry: get_pipeline_jobs API error causes MR removal"

    def given_processor_with_get_pipeline_jobs_raising_api_error(self):
        self.processor = create_mock_processor(settings=create_mock_settings(job_retry_count=1))

        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="failed")

        self.processor.gitlab_client.get_pipeline_jobs = AsyncMock(side_effect=GitLabAPIError("Connection timeout"))

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.retried_jobs: dict[str, int] = {}

    async def when_handle_pipeline_failure_retry_is_called(self):
        (
            self.should_continue,
            self.new_start_time,
            self.updated_retried,
        ) = await self.processor._pipeline_handler.handle_pipeline_failure_retry(
            ctx=self.ctx,
            pipeline=self.pipeline,
            retried_jobs=self.retried_jobs,
        )

    def then_should_continue_is_false(self):
        assert self.should_continue is False

    def and_trigger_pipeline_failed_was_called(self):
        self.mock_sm.trigger_pipeline_failed.assert_awaited_once()
        call_kwargs = self.mock_sm.trigger_pipeline_failed.await_args.kwargs
        assert call_kwargs["retried_jobs"] == {}
        assert call_kwargs["failed_jobs"] == []
