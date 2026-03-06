"""Test _wait_for_rebase returns CONFLICT when check_rebase_status reports conflicts.

Lines 418-424: when check_rebase_status returns (False, True) during polling,
get_mr_conflicts is called, trigger_rebase_failed is triggered, and CONFLICT is returned.
"""

from __future__ import annotations

import vedro

from gitlab_queue.core.processor import ProcessingResult

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase returns CONFLICT when rebase has conflicts during polling"

    def given_processor_with_conflict_during_rebase_poll(self):
        self.processor = create_mock_processor()

        # check_rebase_status → (False, True) = not in progress, has conflicts
        self.processor.gitlab_client.check_rebase_status.return_value = (False, True)
        self.processor.gitlab_client.get_mr_conflicts.return_value = ["README.md"]

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)
        self.ctx.rebase_ctx.old_sha = "abc123"

    async def when_wait_for_rebase_is_called(self):
        self.result = await self.processor._wait_for_rebase(self.ctx)

    def then_result_is_conflict(self):
        assert self.result == ProcessingResult.CONFLICT

    def and_trigger_rebase_failed_was_called(self):
        self.mock_sm.trigger_rebase_failed.assert_awaited_once()

    def and_get_mr_conflicts_was_called(self):
        self.processor.gitlab_client.get_mr_conflicts.assert_awaited_once_with(42)
