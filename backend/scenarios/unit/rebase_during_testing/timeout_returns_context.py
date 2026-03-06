"""Test scenario: timeout during pipeline wait returns None pipeline."""

from __future__ import annotations

import vedro

from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)
from scenarios.fakes import FakeGitLabClient, create_mr, create_pipeline

from ._helpers import MockSettings


class Scenario(vedro.Scenario):
    subject = "timeout waiting for new pipeline returns none and updated context"

    def given_handler_that_will_timeout_on_pipeline_wait(self):
        """
        Set up a rebase handler, FakeGitLabClient, settings, and an initial context
        configured to simulate a pipeline wait timeout.
        """
        mr_needs_rebase = create_mr(
            iid=42,
            has_conflicts=False,
            merge_status="cannot_be_merged",
            sha="old_sha_123",
            rebase_in_progress=False,
        )
        mr_after_rebase = create_mr(
            iid=42,
            has_conflicts=False,
            merge_status="can_be_merged",
            sha="new_sha_456",
            rebase_in_progress=False,
        )

        # Stale pipeline with old SHA to simulate timeout
        stale_pipeline = create_pipeline(
            id=100,
            sha="old_sha_123",
            status="canceled",
        )

        self.gitlab_client = FakeGitLabClient(
            mr_response_sequence=[
                mr_needs_rebase,
                mr_needs_rebase,
                mr_after_rebase,
                mr_after_rebase,
            ],
            latest_pipeline_response=stale_pipeline,
        )
        self.settings = MockSettings(
            rebase_timeout_seconds=60,
            pipeline_poll_interval_seconds=5,
            # Very short timeout to simulate timeout scenario
            post_rebase_pipeline_wait_seconds=0,
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
        Call the rebase handler for MR id 42 using the current test context.
        """
        self.new_ctx, self.new_pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_new_pipeline_should_be_none(self):
        assert self.new_pipeline is None

    def and_rebase_count_should_be_incremented(self):
        assert self.new_ctx.rebase_count == 1

    def and_current_pipeline_id_should_be_none(self):
        assert self.new_ctx.current_pipeline_id is None

    def and_rebase_should_have_been_attempted(self):
        assert self.gitlab_client.rebase_calls == [42]
