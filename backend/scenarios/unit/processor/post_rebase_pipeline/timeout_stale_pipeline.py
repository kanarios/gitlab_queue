"""Test _wait_for_post_rebase_pipeline returns (None, new_sha) when timeout with stale pipeline.

Lines 576-582: when timeout occurs and pipeline SHA doesn't match current SHA,
return (None, new_sha) to avoid acting on a stale pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline returns None new_sha when timeout with stale pipeline"

    def given_processor_with_timeout_and_stale_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        old_sha = "old_sha"
        new_sha = "new_sha_after_rebase"

        # During polling: rebase_in_progress=True → always CONTINUE
        polling_mr = create_mock_mr(iid=42, sha=new_sha)
        polling_mr.rebase_in_progress = True

        # After timeout: get_mr returns the new SHA
        post_timeout_mr = create_mock_mr(iid=42, sha=new_sha)
        post_timeout_mr.rebase_in_progress = False

        self.processor.gitlab_client.get_mr = AsyncMock(side_effect=[polling_mr, post_timeout_mr])

        # After timeout: pipeline has WRONG sha (stale pipeline)
        stale_pipeline = create_mock_pipeline(pipeline_id=100, sha="some_other_sha", status="running")
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = stale_pipeline

        self.old_sha = old_sha
        self.expected_new_sha = new_sha

    async def when_wait_for_post_rebase_pipeline_times_out(self):
        self.returned_pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_pipeline_is_none_due_to_sha_mismatch(self):
        assert self.returned_pipeline is None

    def and_returned_sha_is_new_sha(self):
        assert self.returned_sha == self.expected_new_sha
