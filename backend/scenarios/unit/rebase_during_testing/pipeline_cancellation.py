"""Test scenario: old pipeline is cancelled when rebase starts."""

from __future__ import annotations

import vedro

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from ._helpers import MockSettings


class Scenario(vedro.Scenario):
    subject = "old pipeline is cancelled when rebase during testing starts"

    def given_handler_with_mr_needing_rebase(self):
        """
        Prepare a RebaseDuringTestingHandler with a FakeGitLabClient that simulates
        an MR requiring a rebase, and initialize a context with current_pipeline_id=100.
        """
        mr_needs_rebase = create_mr(
            iid=42,
            has_conflicts=False,
            merge_status="cannot_be_merged",
            sha="old_sha_123",
            rebase_in_progress=False,
        )
        mr_after_cancel = create_mr(
            iid=42,
            has_conflicts=False,
            merge_status="cannot_be_merged",
            sha="old_sha_123",
            rebase_in_progress=False,
        )
        mr_rebased = create_mr(
            iid=42,
            has_conflicts=False,
            merge_status="can_be_merged",
            sha="new_sha_456",
            rebase_in_progress=False,
        )

        new_pipeline = create_pipeline(
            id=200,
            sha="new_sha_456",
            status="running",
        )

        self.gitlab_client = FakeGitLabClient(
            mr_response_sequence=[mr_needs_rebase, mr_after_cancel, mr_rebased, mr_rebased],
            latest_pipeline_response=new_pipeline,
        )
        self.settings = MockSettings(
            rebase_timeout_seconds=60,
            pipeline_poll_interval_seconds=5,
            post_rebase_pipeline_wait_seconds=60,
        )
        self.handler = RebaseDuringTestingHandler(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )
        self.ctx = RebaseDuringTestingContext(
            rebase_count=0,
            max_attempts=3,
            current_pipeline_id=100,
        )

    async def when_handle_rebase_if_needed_is_called(self):
        """
        Invokes the handler's rebase check for merge request 42 and stores the resulting
        context and pipeline on the test instance.
        """
        self.new_ctx, self.new_pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_old_pipeline_should_be_cancelled(self):
        """
        Asserts that the original pipeline was cancelled with pipeline id 100.
        """
        assert self.gitlab_client.cancel_pipeline_calls == [100]

    def and_rebase_should_have_been_initiated(self):
        """
        Asserts that a rebase was initiated for the merge request with ID 42.
        """
        assert self.gitlab_client.rebase_calls == [42]

    def and_new_pipeline_should_be_returned(self):
        """
        Asserts that a new pipeline was returned and its id equals 200.
        """
        assert self.new_pipeline is not None
        assert self.new_pipeline.id == 200

    def and_rebase_count_should_be_incremented(self):
        """
        Asserts that the rebase count in the updated context has been incremented to 1.
        """
        assert self.new_ctx.rebase_count == 1
