"""Test up-to-date MR falls back to retry_pipeline when create_pipeline is rejected.

workflow:rules may block pipelines with source=api (400). Retrying the failed
pipeline on the same SHA is the fallback, as in the post-rebase path.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "up-to-date MR falls back to retry_pipeline when create_pipeline is rejected"

    def given_up_to_date_mr_with_failed_pipeline(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_response=create_pipeline(id=500, sha="abc123", status="failed"),
            create_pipeline_error=GitLabAPIError("No stages/jobs for this pipeline", status_code=400),
            retry_pipeline_response=create_pipeline(id=500, sha="abc123", status="pending"),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_failed_pipeline_was_retried(self):
        assert self.gitlab_client.retry_pipeline_calls == [500]

    def and_testing_started_with_retried_pipeline(self):
        assert self.sm.rebase_complete_calls[0]["pipeline_id"] == 500
