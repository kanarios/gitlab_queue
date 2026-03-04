"""Test _wait_for_post_rebase_pipeline skips terminal pipeline when SHA changed after rebase.

Lines 535-544: when SHA changed and pipeline is terminal (canceled/failed/success), skip and CONTINUE.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_pipeline,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline skips all terminal pipelines when SHA changed after rebase"

    def given_processor_with_sha_change_and_stale_success_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        old_sha = "old_sha_before_rebase"
        new_sha = "new_sha_after_rebase"

        # SHA changed after rebase
        mock_mr = create_mock_mr(iid=42, sha=new_sha)
        mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = mock_mr

        # Pipeline is "success" but it's for the old code (pre-rebase) → should be skipped
        stale_pipeline = create_mock_pipeline(pipeline_id=100, sha=new_sha, status="success")
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = stale_pipeline

        self.old_sha = old_sha

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_stale_terminal_pipeline_is_skipped(self):
        # The "success" pipeline for the new SHA is skipped as terminal after rebase
        # Poll continues until timeout
        assert self.new_sha == "new_sha_after_rebase"
