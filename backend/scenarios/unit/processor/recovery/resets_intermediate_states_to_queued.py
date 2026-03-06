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
        """
        Set up a mocked processor with a queue item for MR IID 42 in the "testing" state and a corresponding mock merge request.

        Creates:
        - a mock processor assigned to self.processor,
        - a test queue item (MR IID 42, state "testing") assigned to self.queue_item and returned by processor.queue_manager.get_active_queue,
        - a mock merge request (IID 42, state "opened", labels ["merge_queue"]) assigned to self.mock_mr and returned by processor.gitlab_client.get_mr.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.add_item(self.queue_item)

        self.mock_mr = create_mock_mr(iid=42, state="opened", labels=["merge_queue"])
        self.processor.gitlab_client.mr_responses[42] = self.mock_mr

    async def when_recover_interrupted_state_is_called(self):
        """
        Invoke the processor's recovery routine to reset merge requests stuck in intermediate states.

        Calls the processor's _recover_interrupted_state method so MRs in states like testing, rebasing, or merging are processed for reset back to the queued state.
        """
        await self.processor._recover_interrupted_state()

    def then_mr_state_is_reset_to_queued(self):
        assert len(self.processor.queue_manager.update_state_calls) == 1
        call = self.processor.queue_manager.update_state_calls[0]
        assert call["mr_iid"] == 42
        assert call["state"] == "queued"
