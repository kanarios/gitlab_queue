"""Test wait_for_post_rebase_pipeline handles race condition when SHA updates on second poll.

Race condition scenario: first poll sees old SHA (fast-forward path), skips stale pipeline.
Second poll sees updated SHA → enters SHA-changed branch → returns new pipeline.

This test confirms the grace period counter does NOT interfere with the race condition path.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr, create_pipeline

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
    exhaustive_poll,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline handles race condition when SHA updates on second poll"

    def given_processor_with_sha_update_on_second_poll(self):
        self.old_sha = "old_sha_abc"
        self.new_sha = "new_sha_def"
        self.old_pipeline_id = 100

        self.processor = create_mock_processor(
            settings=create_mock_settings(pipeline_poll_interval_seconds=0),
            poll_fn=exhaustive_poll,
        )

        self.processor.gitlab_client.mr_response_sequence = [
            create_mr(iid=42, sha=self.old_sha, rebase_in_progress=False),
            create_mr(iid=42, sha=self.new_sha, rebase_in_progress=False),
        ]

        self.new_pipeline = create_pipeline(id=200, sha=self.new_sha, status="running")
        self.processor.gitlab_client.latest_pipeline_sequence = [
            create_pipeline(id=self.old_pipeline_id, sha=self.old_sha, status="success"),
            self.new_pipeline,
        ]

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.returned_pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            old_pipeline_id=self.old_pipeline_id,
            timeout_seconds=60,
        )

    def then_new_pipeline_is_returned(self):
        assert self.returned_pipeline is self.new_pipeline

    def then_returned_sha_is_new(self):
        assert self.returned_sha == self.new_sha
