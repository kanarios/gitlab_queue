"""Test _wait_for_rebase continues polling when waiting for pipeline with correct SHA.

Lines 442-448: when rebase is done but no matching pipeline yet,
log debug and return CONTINUE to keep polling until timeout.
Lines 464-474: timeout is triggered after polling.
"""

from __future__ import annotations

from unittest.mock import patch

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_settings,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase continues polling waiting for pipeline with correct SHA then times out"

    def given_processor_with_rebase_done_but_no_matching_pipeline(self):
        self.processor = create_mock_processor(settings=create_mock_settings(rebase_timeout_seconds=0.001))

        # Rebase is done (not in progress, no conflicts), but no pipeline yet
        self.processor.gitlab_client.check_rebase_status.return_value = (False, False)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.ctx.rebase_ctx.old_sha = "old_sha"

    async def when_wait_for_rebase_is_called_with_no_pipeline(self):
        with patch.object(
            self.processor._rebase_handler,
            "wait_for_post_rebase_pipeline",
            return_value=(None, "new_sha"),
        ):
            self.result = await self.processor._wait_for_rebase(self.ctx)

    def then_result_is_timeout(self):
        assert self.result == ProcessingResult.TIMEOUT

    def and_trigger_timeout_was_called(self):
        self.mock_sm.trigger_timeout.assert_awaited_once()
