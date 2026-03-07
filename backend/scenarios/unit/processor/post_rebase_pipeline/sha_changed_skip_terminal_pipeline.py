"""Test _wait_for_post_rebase_pipeline accepts terminal pipeline when SHA changed.

When SHA changed and pipeline has matching new SHA, it is accepted immediately
regardless of terminal status — it's a valid post-rebase pipeline.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr, create_pipeline

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline accepts terminal pipeline with new SHA"

    def given_processor_with_sha_change_and_terminal_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=0.001))

        old_sha = "old_sha_before_rebase"
        new_sha = "new_sha_after_rebase"

        # SHA changed after rebase
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha=new_sha, rebase_in_progress=False)

        # Pipeline is "success" with matching new SHA → accepted immediately
        self.pipeline_response = create_pipeline(id=100, sha=new_sha, status="success")
        self.processor.gitlab_client.latest_pipeline_response = self.pipeline_response

        self.old_sha = old_sha

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.pipeline, self.new_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=0.001,
        )

    def then_pipeline_is_accepted_on_first_poll(self):
        assert len(self.processor.gitlab_client.get_latest_pipeline_calls) == 1

    def and_pipeline_is_returned(self):
        assert self.pipeline is not None
        assert self.pipeline.id == self.pipeline_response.id

    def and_new_sha_is_updated(self):
        assert self.new_sha == "new_sha_after_rebase"
