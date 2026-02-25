"""Test _recover_interrupted_state skips MR when circuit breaker is open.

When the GitLab circuit breaker is open, recovery should skip the MR
without updating its state and without raising an error.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabCircuitOpenError

from .._helpers import create_mock_processor, create_test_queue_item


class Scenario(vedro.Scenario):
    subject = "recover interrupted state skips MR when circuit breaker open"

    def given_processor_with_circuit_open(self):
        """
        Set up a mock processor whose GitLab client simulates an open circuit breaker and an active queued MR.
        
        Configures:
        - self.processor as a mock processor.
        - self.queue_item as a test queue item with mr_iid 42 and state "queued".
        - processor.queue_manager.get_active_queue to return the created queue item.
        - processor.gitlab_client.get_mr to raise GitLabCircuitOpenError with retry_after=30.
        """
        self.processor = create_mock_processor()

        self.queue_item = create_test_queue_item(mr_iid=42, state="queued")
        self.processor.queue_manager.get_active_queue.return_value = [
            self.queue_item,
        ]

        self.processor.gitlab_client.get_mr.side_effect = GitLabCircuitOpenError("Circuit open", retry_after=30)

    async def when_recover_interrupted_state_is_called(self):
        """
        Calls the processor's _recover_interrupted_state and captures any exception raised.
        
        If an exception occurs while running _recover_interrupted_state, stores the exception in self.raised; otherwise leaves self.raised set to None.
        """
        self.raised = None
        try:
            await self.processor._recover_interrupted_state()
        except Exception as exc:
            self.raised = exc

    def then_no_error_is_raised(self):
        """
        Asserts that no exception was captured during the preceding action.
        
        Raises:
            AssertionError: If self.raised is not None (an exception was captured).
        """
        assert self.raised is None

    def and_mr_state_is_not_updated(self):
        """
        Asserts that the processor did not attempt to update the merge request state.
        
        Raises an AssertionError if queue_manager.update_mr_state was awaited.
        """
        self.processor.queue_manager.update_mr_state.assert_not_awaited()
