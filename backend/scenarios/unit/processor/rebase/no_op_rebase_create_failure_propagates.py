"""Test a no-op rebase whose pipeline cannot be started propagates the error.

When the SHA never changes after rebase, wait_for_rebase hands the MR to the
same path as an up-to-date MR. If GitLab rejects creating a pipeline and there
is no pipeline on the SHA to retry, the error propagates so the processor
requeues the MR with the attempt counted, instead of timing out the rebase.
"""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.types import RebaseContext
from scenarios.fakes import FakeGitLabClient, create_mr

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "no-op rebase propagates error when pipeline cannot be created"

    def given_rebase_that_did_not_change_sha(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123")},
            rebase_status=(False, False),
            latest_pipeline_response=None,
            create_pipeline_error=GitLabAPIError("Pipelines blocked by workflow:rules", status_code=400),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        self.ctx.rebase_ctx = RebaseContext(old_sha="abc123")

    async def when_wait_for_rebase_is_called(self):
        with catched(GitLabAPIError) as self.exc_info:
            await self.handler.wait_for_rebase(self.ctx)

    def then_client_error_propagates(self):
        assert self.exc_info.value.status_code == 400

    def and_rebase_was_not_timed_out(self):
        assert self.sm.timeout_calls == []

    def and_testing_was_not_started(self):
        assert self.sm.rebase_complete_calls == []
