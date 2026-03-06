"""Test _wait_for_post_rebase_pipeline returns (None, old_sha) when shutdown is requested.

Line 559: when shutdown event is set, return (None, old_sha).
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline returns None old_sha when shutdown requested"

    def given_processor_with_shutdown_event_set(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=60))

        mock_mr = create_mock_mr(iid=42, sha="new_sha")
        mock_mr.rebase_in_progress = True  # Would keep polling
        self.processor.gitlab_client.get_mr.return_value = mock_mr
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = None

        # Set shutdown before calling
        self.processor._shutdown_event.set()
        self.old_sha = "old_sha_before_rebase"

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=60,
        )

    def then_pipeline_is_none(self):
        assert self.pipeline is None

    def and_returned_sha_is_old_sha(self):
        assert self.returned_sha == self.old_sha
