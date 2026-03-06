"""Test _wait_for_post_rebase_pipeline returns pipeline when SHA changed and running pipeline found.

Lines 535-542: when SHA changed after rebase and found a pipeline with new SHA that is NOT
in TERMINAL_PIPELINE_STATUSES (e.g. running), log and return DONE with that pipeline.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr, create_pipeline

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline returns running pipeline when SHA changed"

    def given_processor_with_new_sha_and_running_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=60))

        self.old_sha = "old_sha_before_rebase"
        self.new_sha = "new_sha_after_rebase"

        # MR: rebase complete, SHA changed to new_sha
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha=self.new_sha, rebase_in_progress=False)

        # Pipeline: has new SHA, status "running" (NOT in TERMINAL_PIPELINE_STATUSES)
        self.pipeline = create_pipeline(id=200, sha=self.new_sha, status="running")
        self.processor.gitlab_client.latest_pipeline_response = self.pipeline

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.returned_pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=60,
        )

    def then_pipeline_is_returned(self):
        assert self.returned_pipeline is self.pipeline

    def and_returned_sha_is_new_sha(self):
        assert self.returned_sha == self.new_sha
