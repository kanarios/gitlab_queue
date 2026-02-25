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
        """
        Set up a mock processor with an active queued merge request (IID 42) that exists on GitLab but lacks the queue label.
        
        Configures:
        - a mock processor instance,
        - an active queue containing a queue item for MR IID 42 with state "queued",
        - the GitLab client to return a mock MR (IID 42, state "opened") whose labels do not include the queue label.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.get_active_queue.return_value = [
            self.queue_item,
        ]

        self.mock_mr = create_mock_mr(iid=42, state="opened", labels=["other_label"])
        self.processor.gitlab_client.get_mr.return_value = self.mock_mr

    async def when_recover_interrupted_state_is_called(self):
        """
        Trigger the processor to recover interrupted queue processing state.
        """
        await self.processor._recover_interrupted_state()

    def then_mr_is_marked_as_removed(self):
        """
        Asserts that the merge request with IID 42 was marked as removed in the queue manager.
        
        Verifies that queue_manager.update_mr_state was awaited exactly once with arguments (42, "removed").
        """
        self.processor.queue_manager.update_mr_state.assert_awaited_once_with(42, "removed")
