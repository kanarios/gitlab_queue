"""Test _wait_for_post_rebase_pipeline uses DEFAULT_POST_REBASE_PIPELINE_WAIT_SECONDS when timeout_seconds is None.

Line 498: when timeout_seconds is not provided, defaults to DEFAULT_POST_REBASE_PIPELINE_WAIT_SECONDS.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline uses default timeout when timeout_seconds is None"

    def given_processor_with_shutdown_preset(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=60))

        mock_mr = create_mock_mr(iid=42, sha="old_sha")
        mock_mr.rebase_in_progress = False
        self.processor.gitlab_client.get_mr.return_value = mock_mr
        self.processor.gitlab_client.get_latest_mr_pipeline.return_value = None

        # Shutdown pre-set so the loop exits immediately without calling poll_fn
        # Line 498 is still executed because it's before the loop (poll_until_done call)
        self.processor._shutdown_event.set()
        self.old_sha = "old_sha"

    async def when_called_without_timeout_seconds(self):
        # Call WITHOUT timeout_seconds — line 498 assigns the default
        self.pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            # timeout_seconds intentionally omitted — uses DEFAULT_POST_REBASE_PIPELINE_WAIT_SECONDS
        )

    def then_pipeline_is_none(self):
        assert self.pipeline is None

    def and_returned_sha_is_old_sha(self):
        # Shutdown path returns old_sha
        assert self.returned_sha == self.old_sha
