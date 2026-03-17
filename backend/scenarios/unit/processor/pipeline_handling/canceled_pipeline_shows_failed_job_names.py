"""Test canceled pipeline includes failed job names in error message.

When a pipeline is canceled and has multiple failed/canceled jobs,
the error message should list all of them by name.
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
    subject = "canceled pipeline shows failed job names in error message"

    def given_gitlab_client_with_multiple_failed_jobs(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.pipeline_jobs_response = [
            create_job(id=1, name="e2e-tests 1/12", status="failed"),
            create_job(id=2, name="e2e-tests 2/12", status="canceled"),
            create_job(id=3, name="build", status="success"),
            create_job(id=4, name="lint", status="success"),
        ]

    def given_pipeline_handler(self):
        self.handler = create_test_pipeline_handler(gitlab_client=self.gitlab_client)

    def given_canceled_pipeline(self):
        self.pipeline = create_mock_pipeline(pipeline_id=100, sha="abc123", status="canceled")

    def given_processing_context(self):
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_handle_pipeline_status_is_called(self):
        self.result = await self.handler.handle_pipeline_status(
            ctx=self.ctx,
            sm=self.sm,
            pipeline=self.pipeline,
            retried_jobs={},
        )

    def then_result_is_pipeline_failed(self):
        assert self.result == ProcessingResult.PIPELINE_FAILED

    def and_failed_jobs_contains_both_names(self):
        call = self.sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == ["e2e-tests 1/12", "e2e-tests 2/12"]

    def and_error_message_contains_first_job_name(self):
        call = self.sm.pipeline_failed_calls[0]
        assert "e2e-tests 1/12" in call["error_message"]

    def and_error_message_contains_second_job_name(self):
        call = self.sm.pipeline_failed_calls[0]
        assert "e2e-tests 2/12" in call["error_message"]
