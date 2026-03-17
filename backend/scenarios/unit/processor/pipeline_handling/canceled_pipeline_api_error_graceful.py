"""Test canceled pipeline gracefully handles API error when fetching jobs.

When get_pipeline_jobs raises an exception, the handler should fall back
to empty failed_jobs and generic "Pipeline was canceled" message.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient

from .._helpers import (
    create_mock_pipeline,
    create_mock_state_machine,
    create_processing_context,
    create_test_pipeline_handler,
)


class Scenario(vedro.Scenario):
    subject = "canceled pipeline API error falls back to generic message"

    def given_gitlab_client_with_api_error(self):
        self.gitlab_client = FakeGitLabClient()
        self.gitlab_client.pipeline_jobs_response = GitLabAPIError(500, "Internal Server Error")

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

    def and_fallback_message_is_used(self):
        call = self.sm.pipeline_failed_calls[0]
        assert call["error_message"] == "Pipeline was canceled"

    def and_failed_jobs_is_empty(self):
        call = self.sm.pipeline_failed_calls[0]
        assert call["failed_jobs"] == []
