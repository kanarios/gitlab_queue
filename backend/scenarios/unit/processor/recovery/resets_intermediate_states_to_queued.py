"""Test _recover_interrupted_state resets intermediate states to queued.

When the processor restarts and finds an MR in an intermediate state
(rebasing, testing, merging) that is still open in GitLab with the
queue label, it should reset the MR back to 'queued' for re-processing.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "recover interrupted state resets intermediate states to queued"

    def given_processor_with_mr_in_testing_state(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_active_queue.return_value = [
            self.queue_item,
        ]

        self.mock_mr = create_mock_mr(iid=42, state="opened", labels=["merge_queue"])
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

    async def when_recover_interrupted_state_is_called(self):
        await self.processor._recover_interrupted_state()

    def then_mr_state_is_reset_to_queued(self):
        self.processor.queue_manager.update_mr_state.assert_awaited_once_with(42, "queued")
