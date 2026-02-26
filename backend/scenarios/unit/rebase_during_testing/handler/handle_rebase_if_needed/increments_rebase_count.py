"""Test handle_rebase_if_needed returns ctx with rebase_count+1."""

import asyncio

import vedro

from ..._helpers import (
    MockMergeRequest,
    MockPipeline,
    create_context,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed returns ctx with rebase_count+1"

    def given_handler_with_needs_rebase(self):
        mr = MockMergeRequest(
            merge_status="cannot_be_merged",
            has_conflicts=False,
            sha="new_sha_after_rebase",
        )
        pipeline = MockPipeline(id=999, sha="new_sha_after_rebase")
        self.client = create_mock_gitlab_client(mr=mr, pipeline=pipeline)
        self.handler = create_handler(gitlab_client=self.client)
        self.handler.set_shutdown_event(asyncio.Event())
        self.ctx = create_context(rebase_count=1, max_attempts=3)

    async def when_handle_rebase_if_needed_is_called(self):
        self.new_ctx, self.pipeline = await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_rebase_count_is_incremented(self):
        assert self.new_ctx.rebase_count == 2

    def and_max_attempts_is_preserved(self):
        assert self.new_ctx.max_attempts == 3
