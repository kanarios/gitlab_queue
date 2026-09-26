"""Test up-to-date MR raises when no pipeline can be started before timeout.

Returning a plain ERROR would leave the MR stuck in rebasing without
counting the attempt, so the handler raises and lets the processor's
error handling requeue it.
"""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabAPIError, GitLabServerError
from scenarios.fakes import FakeGitLabClient, create_mr

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "up-to-date MR raises when pipeline cannot be started in time"

    def given_up_to_date_mr_and_failing_create(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_response=None,
            create_pipeline_error=GitLabServerError("Service Unavailable", status_code=503),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        with catched(GitLabAPIError) as self.exc_info:
            await self.handler.process_rebase(self.ctx)

    def then_error_is_raised(self):
        assert "up-to-date MR !42" in str(self.exc_info.value)

    def and_testing_was_not_started(self):
        assert self.sm.rebase_complete_calls == []

    def and_rebase_was_not_called(self):
        assert self.gitlab_client.rebase_calls == []
