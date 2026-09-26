"""Test up-to-date MR retries pipeline creation after a transient 5xx.

The MR and pipeline are re-read before the next attempt, so a pipeline
GitLab managed to create despite the error is picked up instead of
creating a duplicate.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler, exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "up-to-date MR picks up pipeline after create_pipeline server error"

    def given_up_to_date_mr_and_flaky_create(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_sequence=[
                None,  # pre-rebase capture: no pipeline yet
                create_pipeline(id=700, sha="abc123", status="pending"),  # re-read after 5xx
            ],
            create_pipeline_error=GitLabServerError("Bad Gateway", status_code=502),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client, poll_fn=exhaustive_poll)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_success(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_pipeline_creation_was_attempted_once(self):
        assert len(self.gitlab_client.create_pipeline_calls) == 1

    def and_mr_was_re_read_before_retry(self):
        assert self.gitlab_client.get_mr_calls == [42, 42]

    def and_testing_started_with_found_pipeline(self):
        assert self.sm.rebase_complete_calls[0]["pipeline_id"] == 700
