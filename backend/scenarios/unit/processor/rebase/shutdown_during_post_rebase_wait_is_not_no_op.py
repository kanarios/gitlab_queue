"""Test shutdown during the post-rebase wait is not mistaken for a no-op rebase.

wait_for_post_rebase_pipeline returns (None, old_sha) both on shutdown and when
the SHA never changed. Only the latter means the rebase was a no-op; on
shutdown no pipeline must be created and testing must not start.
"""

from __future__ import annotations

from typing import Any

import vedro

from gitlab_queue.core.polling import PollOutcome, PollStatus
from gitlab_queue.core.types import ProcessingResult, RebaseContext
from scenarios.fakes import FakeGitLabClient, create_mr

from .._helpers import create_mock_state_machine, create_processing_context, create_test_rebase_handler


class Scenario(vedro.Scenario):
    subject = "shutdown during post-rebase wait does not start testing"

    def given_shutdown_requested_while_waiting_for_pipeline(self):
        async def poll_with_shutdown_in_post_rebase_wait(config, fn, shutdown_event, **_: Any) -> PollOutcome[Any]:
            if config.operation_name == "post_rebase_pipeline":
                shutdown_event.set()
                return PollOutcome(completed=False, timed_out=False, shutdown_requested=True, result=None)
            status, result = await fn()
            done = status == PollStatus.DONE
            return PollOutcome(completed=done, timed_out=not done, shutdown_requested=False, result=result)

        self.gitlab_client = FakeGitLabClient(
            mr_responses={42: create_mr(iid=42, sha="abc123")},
            rebase_status=(False, False),
            latest_pipeline_response=None,
        )
        self.handler = create_test_rebase_handler(
            gitlab_client=self.gitlab_client,
            poll_fn=poll_with_shutdown_in_post_rebase_wait,
        )
        self.sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.sm)
        self.ctx.rebase_ctx = RebaseContext(old_sha="abc123")

    async def when_wait_for_rebase_is_called(self):
        self.result = await self.handler.wait_for_rebase(self.ctx)

    def then_no_pipeline_was_created(self):
        assert self.gitlab_client.create_pipeline_calls == []

    def and_testing_was_not_started(self):
        assert self.sm.rebase_complete_calls == []

    def and_result_is_not_success(self):
        assert self.result != ProcessingResult.SUCCESS
