"""Test wait_for_post_rebase_pipeline skips stale pipeline by ID after rebase.

Race condition scenario: rebase_in_progress is already false, but mr.sha
hasn't updated yet. The old pipeline (id=100, sha=old_sha, status=success)
is still returned. Without the fix, the bot accepts it and merges with
wrong SHA → 409 Conflict.

With the fix: pipeline.id == old_pipeline_id → skip, wait for new pipeline.
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
    subject = "wait_for_post_rebase_pipeline skips stale pipeline when pipeline ID matches old"

    def given_processor_with_stale_then_new_pipeline(self):
        self.processor = create_mock_processor(
            settings=create_mock_settings(pipeline_poll_interval_seconds=0),
            poll_fn=exhaustive_poll,
        )

        self.old_sha = "old_sha_abc"
        self.new_sha = "new_sha_def"
        self.old_pipeline_id = 100

        # Simulate race condition:
        # 1st get_mr: SHA not yet updated (old_sha)
        # 2nd get_mr: SHA updated (new_sha)
        self.processor.gitlab_client.mr_response_sequence = [
            create_mr(iid=42, sha=self.old_sha, rebase_in_progress=False),
            create_mr(iid=42, sha=self.new_sha, rebase_in_progress=False),
        ]

        # 1st get_latest_pipeline: stale pipeline (id=100, old_sha, success)
        # 2nd get_latest_pipeline: new pipeline (id=200, new_sha, running)
        self.new_pipeline = create_pipeline(id=200, sha=self.new_sha, status="running")
        self.processor.gitlab_client.latest_pipeline_sequence = [
            create_pipeline(id=100, sha=self.old_sha, status="success"),
            self.new_pipeline,
        ]

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.returned_pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            old_pipeline_id=self.old_pipeline_id,
            timeout_seconds=60,
        )

    def then_stale_pipeline_is_skipped(self):
        assert self.returned_pipeline is self.new_pipeline

    def and_returned_sha_is_new_sha(self):
        assert self.returned_sha == self.new_sha
