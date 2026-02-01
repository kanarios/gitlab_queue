"""Test handle_rebase_if_needed calls cancel_pipeline for current_pipeline_id."""

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
    subject = "handle_rebase_if_needed calls cancel_pipeline for current_pipeline_id"

    def given_handler_with_needs_rebase_and_current_pipeline(self):
        mr = MockMergeRequest(
            merge_status="cannot_be_merged",
            has_conflicts=False,
            sha="new_sha_after_rebase",
        )
        pipeline = MockPipeline(id=999, sha="new_sha_after_rebase")
        self.client = create_mock_gitlab_client(mr=mr, pipeline=pipeline)
        self.handler = create_handler(gitlab_client=self.client)
        self.handler.set_shutdown_event(asyncio.Event())
        self.ctx = create_context(current_pipeline_id=123)

    async def when_handle_rebase_if_needed_is_called(self):
        await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_cancel_pipeline_was_called_with_current_id(self):
        self.client.cancel_pipeline.assert_called_once_with(123)
