"""Test _wait_for_rebase_quick raises GitLabAPIError on timeout.

When poll_until_done returns a PollOutcome with timed_out=True,
_wait_for_rebase_quick should raise a GitLabAPIError indicating
that the rebase operation timed out during retry.
"""

from __future__ import annotations

from unittest.mock import patch

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError
from gitlab_queue.core.polling import PollOutcome

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait for rebase quick raises api error on timeout"

    def given_processor_with_rebase_timing_out(self):
        """
        Set up a mock processor, a mock state machine and processing context, and a PollOutcome representing a timed-out poll for use in the test.
        
        Attributes set on self:
            processor: Mock processor instance created by create_mock_processor().
            mock_sm: Mock state machine created by create_mock_state_machine().
            ctx: Processing context for merge request iid 42 containing the mock state machine.
            timed_out_outcome: PollOutcome with completed=False, timed_out=True, shutdown_requested=False, result=None.
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        self.timed_out_outcome = PollOutcome(
            completed=False,
            timed_out=True,
            shutdown_requested=False,
            result=None,
        )

    async def when_wait_for_rebase_quick_is_called(self):
        self.raised = None
        with patch(
            "gitlab_queue.core.processor.poll_until_done",
            return_value=self.timed_out_outcome,
        ):
            try:
                await self.processor._wait_for_rebase_quick(self.ctx)
            except GitLabAPIError as exc:
                self.raised = exc

    def then_api_error_is_raised(self):
        """
        Verify that a GitLabAPIError was raised and stored on the scenario.
        
        Asserts that `self.raised` is not None and that it is an instance of `GitLabAPIError`.
        """
        assert self.raised is not None
        assert isinstance(self.raised, GitLabAPIError)

    def and_error_message_mentions_timeout(self):
        """
        Asserts that the caught exception's message contains the word "timeout".
        
        Checks the stored exception in `self.raised` and fails the test if its string representation does not include "timeout" (case-insensitive).
        """
        assert "timeout" in str(self.raised).lower()
