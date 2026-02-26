"""Test _wait_for_new_pipeline accepts pipeline with different ID."""

import asyncio

import vedro

from ..._helpers import (
    MockMergeRequest,
    MockPipeline,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "_wait_for_new_pipeline accepts pipeline with different ID immediately"

    def given_handler_with_new_pipeline(self):
        self.old_sha = "old_sha_before_rebase"
        self.new_sha = "new_sha_after_rebase"
        self.old_pipeline_id = 100
        self.new_pipeline_id = 200

        # MR already has new SHA after rebase
        mr = MockMergeRequest(sha=self.new_sha, rebase_in_progress=False)

        # Pipeline has different ID from old one
        new_pipeline = MockPipeline(
            id=self.new_pipeline_id,
            sha=self.new_sha,
            status="running",
        )

        self.client = create_mock_gitlab_client(mr=mr, pipeline=new_pipeline)
        self.handler = create_handler(gitlab_client=self.client)
        self.handler.set_shutdown_event(asyncio.Event())

    async def when_wait_for_new_pipeline_is_called(self):
        self.result = await self.handler._wait_for_new_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            old_pipeline_id=self.old_pipeline_id,
        )

    def then_new_pipeline_is_returned(self):
        assert self.result is not None
        assert self.result.id == self.new_pipeline_id

    def then_pipeline_was_fetched_once(self):
        self.client.get_latest_mr_pipeline.assert_awaited_once()
