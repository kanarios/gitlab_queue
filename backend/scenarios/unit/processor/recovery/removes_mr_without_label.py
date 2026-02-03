"""Test _recover_interrupted_state removes MR without queue label.

When the processor restarts and finds an MR that is still open in GitLab
but no longer has the queue label, it should mark the MR as 'removed'.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "recover interrupted state removes MR without queue label"

    def given_processor_with_unlabeled_mr_in_queue(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.get_active_queue.return_value = [
            self.queue_item,
        ]

        self.mock_mr = create_mock_mr(iid=42, state="opened", labels=["other_label"])
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

    async def when_recover_interrupted_state_is_called(self):
        await self.processor._recover_interrupted_state()

    def then_mr_is_marked_as_removed(self):
        self.processor.queue_manager.update_mr_state.assert_called_once_with(42, "removed")
