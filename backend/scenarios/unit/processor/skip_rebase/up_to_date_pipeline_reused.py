"""Test process_rebase reuses the current pipeline when MR is already up-to-date.

With zero diverged commits there is nothing to rebase: calling the rebase API
would be a no-op, so the handler goes straight to testing with the existing
pipeline on the MR's SHA.
"""

from __future__ import annotations

import vedro
from vedro import params

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "up-to-date MR reuses {status} pipeline without rebase"

    @params("success")
    @params("running")
    @params("pending")
    def __init__(self, status: str):
        self.status = status

    def given_up_to_date_mr_with_pipeline(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_response=create_pipeline(id=500, sha="abc123", status=self.status),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_rebase_was_not_called(self):
        assert self.gitlab_client.rebase_calls == []

    def and_no_pipeline_was_created(self):
        assert self.gitlab_client.create_pipeline_calls == []

    def and_testing_started_with_existing_pipeline(self):
        assert len(self.sm.rebase_complete_calls) == 1
        call = self.sm.rebase_complete_calls[0]
        assert call["pipeline_id"] == 500
        assert call["expected_sha"] == "abc123"

    def and_divergence_was_requested(self):
        assert self.gitlab_client.get_mr_diverged_flags == [True]
