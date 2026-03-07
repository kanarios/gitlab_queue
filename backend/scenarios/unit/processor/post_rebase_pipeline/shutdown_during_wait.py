"""Test _wait_for_post_rebase_pipeline returns (None, old_sha) when shutdown is requested.

Line 559: when shutdown event is set, return (None, old_sha).
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline returns None old_sha when shutdown requested"

    def given_processor_with_shutdown_event_set(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=60))

        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha="new_sha", rebase_in_progress=True)
        self.processor.gitlab_client.latest_pipeline_response = None

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
