"""Test _wait_for_post_rebase_pipeline skips terminal pipeline during polling when SHA changed.

When SHA changed and pipeline is terminal (canceled/failed/success), polling skips it
via CONTINUE. After timeout, the post-timeout path returns the pipeline as-is since
its SHA matches the current MR SHA.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr, create_pipeline

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline skips terminal pipeline during polling but returns it on timeout"

    def given_processor_with_sha_change_and_stale_success_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        old_sha = "old_sha_before_rebase"
        new_sha = "new_sha_after_rebase"

        # SHA changed after rebase
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha=new_sha, rebase_in_progress=False)

        # Pipeline is "success" with matching SHA → skipped during polling, returned on timeout
        self.stale_pipeline = create_pipeline(id=100, sha=new_sha, status="success")
        self.processor.gitlab_client.latest_pipeline_response = self.stale_pipeline

        self.old_sha = old_sha

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_terminal_pipeline_was_skipped_during_polling(self):
        # Polling skipped the terminal pipeline multiple times before timeout
        assert len(self.processor.gitlab_client.get_latest_pipeline_calls) > 1

    def and_pipeline_is_returned_on_timeout(self):
        # After timeout, post-timeout path returns pipeline since SHA matches
        assert self.pipeline is not None
        assert self.pipeline.id == self.stale_pipeline.id

    def and_new_sha_is_updated(self):
        assert self.new_sha == "new_sha_after_rebase"
