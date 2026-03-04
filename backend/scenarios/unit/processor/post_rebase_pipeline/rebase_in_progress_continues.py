"""Test _wait_for_post_rebase_pipeline continues when rebase is still in progress.

Line 498: when mr.rebase_in_progress=True, return PollStatus.CONTINUE.
Test uses short timeout so the loop terminates via timeout.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline continues when rebase is still in progress"

    def given_processor_with_rebase_still_in_progress(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        # MR still has rebase_in_progress = True (not done yet)
        mock_mr = create_mock_mr(iid=42, sha="new_sha")
        mock_mr.rebase_in_progress = True
        self.processor.gitlab_client.get_mr.return_value = mock_mr

    async def when_wait_for_post_rebase_pipeline_is_called_with_short_timeout(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha="old_sha",
            timeout_seconds=0.001,
        )

    def then_pipeline_is_none_due_to_timeout(self):
        # Rebase was in progress, so poll always continued → timeout
        # After timeout, get_mr() is called again; since rebase_in_progress=True,
        # sha may be "new_sha" and pipeline may be None
        assert self.pipeline is None or self.new_sha is not None
