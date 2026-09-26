"""Test process_rebase waits for a running rebase instead of starting another.

A rebase may already be running when the MR is picked up (started from the
GitLab UI). The MR is not up-to-date yet, but PUT /rebase would be rejected
with 409 and reported as a conflict, so the running rebase is awaited.
"""

from __future__ import annotations

import vedro
from vedro import params

from gitlab_queue.core.processor import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler, exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "process_rebase awaits a running rebase (diverged_commits_count={diverged})"

    @params(0)
    @params(3)
    @params(None)
    def __init__(self, diverged: int | None):
        self.diverged = diverged

    def given_mr_with_rebase_running(self):
        self.gitlab_client = FakeGitLabClient(
            mr_response_sequence=[
                create_mr(iid=42, sha="old_sha", rebase_in_progress=True, diverged_commits_count=self.diverged),
            ],
            mr_responses={42: create_mr(iid=42, sha="new_sha")},
            rebase_status_sequence=[(True, False), (False, False)],
            latest_pipeline_response=create_pipeline(id=200, sha="new_sha", status="running"),
        )
        self.handler = create_test_rebase_handler(gitlab_client=self.gitlab_client, poll_fn=exhaustive_poll)
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_it_succeeds(self):
        assert self.result == ProcessingResult.SUCCESS

    def and_no_rebase_was_started(self):
        assert self.gitlab_client.rebase_calls == []

    def and_rebase_status_was_polled_until_done(self):
        assert self.gitlab_client.check_rebase_status_calls == [42, 42]

    def and_testing_started_with_post_rebase_pipeline(self):
        assert self.sm.rebase_complete_calls[0]["pipeline_id"] == 200
        assert self.sm.rebase_complete_calls[0]["expected_sha"] == "new_sha"
