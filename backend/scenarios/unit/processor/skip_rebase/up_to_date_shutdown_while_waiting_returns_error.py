"""Test skip path returns ERROR when shutdown is requested while waiting for a pipeline.

Mirrors wait_for_rebase: on shutdown the MR is left for restart recovery
instead of raising, and testing is not started.
"""

from __future__ import annotations

import asyncio

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import FakeGitLabClient, create_mr

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler, exhaustive_poll


class Scenario(vedro.Scenario):
    subject = "skip path returns ERROR on shutdown while waiting for pipeline"

    def given_up_to_date_mr_with_failing_create_and_shutdown_requested(self):
        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123", diverged_commits_count=0)},
            latest_pipeline_response=None,
            create_pipeline_error=GitLabServerError("Service Unavailable", status_code=503),
        )
        shutdown_event = asyncio.Event()
        shutdown_event.set()
        self.handler = create_test_rebase_handler(
            gitlab_client=self.gitlab_client,
            poll_fn=exhaustive_poll,
            shutdown_event=shutdown_event,
        )
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)

    async def when_process_rebase_is_called(self):
        self.result = await self.handler.process_rebase(self.ctx)

    def then_result_is_error(self):
        assert self.result == ProcessingResult.ERROR

    def and_testing_was_not_started(self):
        assert self.sm.rebase_complete_calls == []
