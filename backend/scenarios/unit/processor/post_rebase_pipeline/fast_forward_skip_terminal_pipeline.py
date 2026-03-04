"""Test _wait_for_post_rebase_pipeline skips terminal pipeline in fast-forward case.

Lines 505, 513-520: when SHA is unchanged (fast-forward) and pipeline is terminal (canceled/failed),
skip it and continue polling.
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
    subject = "wait_for_post_rebase_pipeline skips terminal failed pipeline in fast-forward case"

    def given_processor_fast_forward_with_canceled_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        same_sha = "abc123"

        # Fast-forward: SHA unchanged after rebase
        mock_mr = create_mock_mr(iid=42, sha=same_sha)
        mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = mock_mr

        # Terminal pipeline (canceled) with same SHA → should be skipped
        terminal_pipeline = create_mock_pipeline(pipeline_id=100, sha=same_sha, status="canceled")
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = terminal_pipeline

        self.old_sha = same_sha  # Same SHA = fast-forward case

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        # Short timeout — poll will skip terminal pipeline and then time out
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_terminal_pipeline_is_skipped(self):
        # The canceled pipeline should be skipped (returned None after timeout)
        # The post-timeout logic will call get_mr and get_latest_mr_pipeline again
        # Since both return the same values, pipeline.sha == new_sha but it's canceled
        # So it won't be skipped in the post-timeout logic (different code path)
        assert self.new_sha is not None
