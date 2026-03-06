"""Test _recover_interrupted_state removes closed MR from queue.

When the processor restarts and finds an MR that has been closed in GitLab,
it should mark the MR as 'removed' in the queue.
"""

from __future__ import annotations

import vedro

from .._helpers import (
    create_mock_mr,
    create_mock_processor,
    create_test_queue_item,
)


class Scenario(vedro.Scenario):
    subject = "recover interrupted state removes closed MR from queue"

    def given_processor_with_closed_mr_in_queue(self):
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.add_item(self.queue_item)

        self.mock_mr = create_mock_mr(iid=42, state="closed", labels=["merge_queue"])
        self.processor.gitlab_client.mr_responses[42] = self.mock_mr

    async def when_recover_interrupted_state_is_called(self):
        await self.processor._recover_interrupted_state()

    def then_mr_is_marked_as_removed(self):
        """
        Assert that the queue marks merge request IID 42 as removed.

        Verifies that queue_manager.complete_mr was awaited exactly once with status "removed"
        and a failure_reason indicating recovery.
        """
        assert len(self.processor.queue_manager.complete_calls) == 1
        call = self.processor.queue_manager.complete_calls[0]
        assert call["mr_iid"] == 42
        assert call["status"] == "removed"
        assert call["failure_reason"] == "closed_during_recovery"
