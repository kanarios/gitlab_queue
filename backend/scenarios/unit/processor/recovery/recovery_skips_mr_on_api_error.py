"""Test _recover_interrupted_state skips MR on GitLabAPIError.

When get_mr raises a GitLabAPIError for one of the active queue items,
the recovery process should skip that MR without updating its state,
allowing it to be retried on the next recovery attempt.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "recover interrupted state skips MR on GitLab API error"

    def given_processor_with_api_error_for_mr(self):
        """
        Prepare a mock processor with an active queue containing a merge request (IID 42) in the "testing" state and configure its GitLab client to raise GitLabAPIError when fetching that MR.

        Sets:
            - self.processor: mock processor
            - self.queue_item: test queue item for MR IID 42
            - processor.queue_manager.get_active_queue to return a list with the queue item
            - processor.gitlab_client.get_mr to raise GitLabAPIError("API unavailable")
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="testing")
        self.processor.queue_manager.get_active_queue.return_value = [
            self.queue_item,
        ]

        self.processor.gitlab_client.get_mr.side_effect = GitLabAPIError("API unavailable")

    async def when_recover_interrupted_state_is_called(self):
        """
        Invoke the processor's interrupted-state recovery and capture any exception in self.raised.

        Sets self.raised to the caught exception if one occurs; leaves it as None if no exception is raised.
        """
        self.raised = None
        try:
            await self.processor._recover_interrupted_state()
        except Exception as exc:
            self.raised = exc

    def then_no_error_is_raised(self):
        """
        Asserts that no exception was raised during the tested operation.

        Fails the test if self.raised is not None.
        """
        assert self.raised is None

    def and_update_mr_state_is_not_called(self):
        """
        Asserts that the queue manager's update_mr_state was not awaited during recovery.

        Verifies that no merge request state update was attempted after a GitLab API error.
        """
        self.processor.queue_manager.update_mr_state.assert_not_awaited()
