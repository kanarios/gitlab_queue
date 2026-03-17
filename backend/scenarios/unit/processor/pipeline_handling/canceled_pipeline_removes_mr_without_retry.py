"""Test canceled pipeline removes MR without attempting job retry.

When a pipeline is canceled, the processor should trigger pipeline_failed
with failed/canceled job names from the pipeline (if fetchable).
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_job

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
)


class Scenario(vedro.Scenario):
    subject = "canceled pipeline removes MR without retry"

    def given_gitlab_client_with_canceled_job(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.pipeline_jobs_response = [
            create_job(id=1, name="e2e-tests 1/12", status="canceled"),
            create_job(id=2, name="build", status="success"),
        ]

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(gitlab_client=self.gitlab_client)

    def given_canceled_pipeline(self):
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled")

    def given_processing_context(self):
        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.mock_sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_error_message_mentions_canceled(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "canceled" in call["error_message"].lower()

    def and_error_message_contains_job_name(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert "e2e-tests 1/12" in call["error_message"]

    def and_failed_jobs_list_contains_canceled_job(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == ["e2e-tests 1/12"]

    def and_retried_jobs_is_empty(self):
        call = self.mock_sm.pipeline_failed_calls[0]
        assert call["retried_jobs"] == {}

    def and_retry_pipeline_job_was_not_called(self):
        assert len(self.gitlab_client.retry_job_calls) == 0
