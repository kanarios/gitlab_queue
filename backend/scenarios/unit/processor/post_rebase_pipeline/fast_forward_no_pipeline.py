"""Test _wait_for_post_rebase_pipeline continues when SHA unchanged and no pipeline found.

Line 522: when fast-forward (SHA unchanged) and get_latest_mr_pipeline returns None, CONTINUE.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline continues when fast-forward and no pipeline found"

    def given_processor_fast_forward_with_no_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        same_sha = "abc123"

        # Fast-forward: SHA unchanged after rebase
        mock_mr = create_mock_mr(iid=42, sha=same_sha)
        mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = mock_mr

        # No pipeline found yet
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = None

        self.old_sha = same_sha

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_result_is_no_pipeline_due_to_timeout(self):
        # No pipeline found, poll continues until timeout, then returns (None, sha)
        assert self.pipeline is None

    def and_new_sha_matches_old_sha(self):
        assert self.new_sha == self.old_sha
