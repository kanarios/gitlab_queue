"""Test _wait_for_post_rebase_pipeline continues when SHA changed but no matching pipeline.

Line 544: when SHA changed after rebase and no pipeline found (or pipeline has wrong SHA),
return PollStatus.CONTINUE — loop continues until found or shutdown/timeout.
"""

from __future__ import annotations

import vedro

from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_post_rebase_pipeline continues when SHA changed but no pipeline matches"

    def given_processor_with_new_sha_but_no_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(pipeline_poll_interval_seconds=60))

        self.old_sha = "old_sha_before_rebase"
        self.new_sha = "new_sha_after_rebase"

        # MR: SHA changed to new_sha, rebase complete
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha=self.new_sha, rebase_in_progress=False)

        # No pipeline found → CONTINUE
        self.processor.gitlab_client.latest_pipeline_response = None

        # Set shutdown after the first get_mr call so the loop exits cleanly
        original_get_mr = self.processor.gitlab_client.get_mr
        call_count = 0

        async def get_mr_and_trigger_shutdown(mr_iid: int):
            nonlocal call_count
            call_count += 1
            result = await original_get_mr(mr_iid)
            if call_count == 1:
                self.processor._shutdown_event.set()
            return result

        self.processor.gitlab_client.get_mr = get_mr_and_trigger_shutdown

    async def when_wait_for_post_rebase_pipeline_is_called(self):
        self.returned_pipeline, self.returned_sha = await self.processor._rebase_handler.wait_for_post_rebase_pipeline(
            mr_iid=42,
            old_sha=self.old_sha,
            timeout_seconds=60,
        )

    def then_pipeline_is_none(self):
        # Shutdown path → (None, old_sha)
        assert self.returned_pipeline is None

    def and_sha_is_returned(self):
        # Shutdown triggered after line 544 was executed
        assert self.returned_sha == self.old_sha
