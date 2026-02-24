"""Test _wait_for_new_pipeline accepts any pipeline when old_pipeline_id is None."""

import asyncio

import vedro

from ..._helpers import (
    MockMergeRequest,
    MockPipeline,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "_wait_for_new_pipeline accepts any valid pipeline when old_pipeline_id is None"

    def given_handler_with_pipeline_and_no_old_id(self):
        self.old_sha = "old_sha_before_rebase"
        self.new_sha = "new_sha_after_rebase"
        self.pipeline_id = 100

        # MR already has new SHA after rebase
        mr = MockMergeRequest(sha=self.new_sha, rebase_in_progress=False)

        # Pipeline exists with any ID (backwards compatible case)
        pipeline = MockPipeline(
            id=self.pipeline_id,
            sha=self.new_sha,
            status="running",
        )

        self.client = create_mock_gitlab_client(mr=mr, pipeline=pipeline)
        self.handler = create_handler(gitlab_client=self.client)
        self.handler.set_shutdown_event(asyncio.Event())

    async def when_wait_for_new_pipeline_is_called_without_old_id(self):
        self.result = await self.handler._wait_for_new_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            old_pipeline_id=None,
        )

    def then_pipeline_is_accepted(self):
        assert self.result is not None
        assert self.result.id == self.pipeline_id

    def then_pipeline_was_fetched_once(self):
        self.client.get_latest_mr_pipeline.assert_awaited_once()
