"""BUG-5: Recovery should move merged MRs to history via complete_mr.

When an MR is in 'testing' state locally but GitLab shows it as 'merged',
recovery should call complete_mr to properly move it to the history table.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from scenarios.unit.processor._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "recovery moves merged MR to history via complete_mr"

    def given_processor_with_testing_item_but_gitlab_state_merged(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_active_queue.return_value = [self.queue_item]
        self.processor.queue_manager.complete_mr = AsyncMock(return_value=True)

        self.processor.gitlab_client.get_mr.return_value = create_mock_mr(
            iid=42,
            state="merged",
            labels=["merge_queue"],
        )

    async def when_recovery_runs(self):
        await self.processor._recover_interrupted_state()

    def then_complete_mr_is_called(self):
        assert self.processor.queue_manager.complete_mr.await_count == 1, (
            "Expected queue_manager.complete_mr to be awaited once, "
            f"got {self.processor.queue_manager.complete_mr.await_count}"
        )
        call = self.processor.queue_manager.complete_mr.await_args
        assert call.args[0] == 42
        assert call.kwargs.get("status") == "merged"
