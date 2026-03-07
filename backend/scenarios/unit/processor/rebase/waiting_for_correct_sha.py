"""Test _wait_for_rebase continues polling when waiting for pipeline with correct SHA.

Lines 442-448: when rebase is done but no matching pipeline yet,
log debug and return CONTINUE to keep polling until timeout.
Lines 464-474: timeout is triggered after polling.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.types import ProcessingResult
from scenarios.fakes import create_mr

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase continues polling waiting for pipeline with correct SHA then times out"

    def given_processor_with_rebase_done_but_no_matching_pipeline(self):
        self.processor = create_mock_processor(
            settings=create_mock_settings(
                rebase_timeout_seconds=0.001,
                post_rebase_pipeline_wait_seconds=0.001,
                pipeline_poll_interval_seconds=0.001,
            ),
        )

        # Rebase is done (not in progress, no conflicts), but no pipeline yet
        self.processor.gitlab_client.rebase_status = (False, False)
        # MR returns new SHA (different from old), no pipeline available
        self.processor.gitlab_client.mr_responses[42] = create_mr(iid=42, sha="new_sha")
        self.processor.gitlab_client.latest_pipeline_response = None

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.ctx.rebase_ctx.old_sha = "old_sha"

    async def when_wait_for_rebase_is_called_with_no_pipeline(self):
        self.result = await self.processor._wait_for_rebase(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT

    def and_trigger_timeout_was_called(self):
        assert len(self.mock_sm.timeout_calls) == 1
