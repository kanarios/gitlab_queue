"""Test up-to-date MR does not retry a pipeline that ran on another SHA.

Retrying such a pipeline would test outdated code, so when create_pipeline
is rejected the error propagates and the processor requeues the MR.
"""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "up-to-date MR does not retry pipeline from another SHA"

    def given_up_to_date_mr_with_pipeline_on_old_sha(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_response=create_pipeline(id=500, sha="old999", status="failed"),
            create_pipeline_error=GitLabAPIError("No stages/jobs for this pipeline", status_code=400),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        with catched(GitLabAPIError) as self.exc_info:
            await self.handler.process_rebase(self.ctx)

    def then_client_error_propagates(self):
        assert self.exc_info.value.status_code == 400

    def and_old_pipeline_was_not_retried(self):
        assert self.gitlab_client.retry_pipeline_calls == []

    def and_testing_was_not_started(self):
        assert self.sm.rebase_complete_calls == []
