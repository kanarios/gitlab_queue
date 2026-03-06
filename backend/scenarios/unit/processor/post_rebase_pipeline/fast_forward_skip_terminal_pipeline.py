"""Test _wait_for_post_rebase_pipeline skips terminal pipeline during polling in fast-forward case.

When SHA is unchanged (fast-forward) and pipeline is terminal (canceled/failed),
polling skips it via CONTINUE. After timeout, the post-timeout path returns
the pipeline since its SHA matches.
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
    subject = "wait_for_post_rebase_pipeline skips terminal pipeline during polling but returns it on timeout"

    def given_processor_fast_forward_with_canceled_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        same_sha = "abc123"

        # Fast-forward: SHA unchanged after rebase
        mock_mr = create_mock_mr(iid=42, sha=same_sha)
        mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = mock_mr

        # Terminal pipeline (canceled) with same SHA → skipped during polling, returned on timeout
        self.terminal_pipeline = create_mock_pipeline(pipeline_id=100, sha=same_sha, status="canceled")
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = self.terminal_pipeline

        self.old_sha = same_sha  # Same SHA = fast-forward case

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_terminal_pipeline_was_skipped_during_polling(self):
        # Polling skipped the canceled pipeline multiple times before timeout
        assert self.processor.gitlab_client.get_latest_mr_pipeline.call_count > 1

    def and_pipeline_is_returned_on_timeout(self):
        # After timeout, post-timeout path returns pipeline since SHA matches
        assert self.pipeline is self.terminal_pipeline

    def and_new_sha_matches_old_sha(self):
        assert self.new_sha == self.old_sha
