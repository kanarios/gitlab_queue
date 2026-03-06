"""Test _wait_for_rebase_quick raises GitLabAPIError on timeout.

When poll_fn returns a PollOutcome with timed_out=True,
_wait_for_rebase_quick should raise a GitLabAPIError indicating
that the rebase operation timed out during retry.
"""

from __future__ import annotations

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
        Set up a mock processor with an injected poll_fn that returns a timed-out
        PollOutcome, a mock state machine and processing context.

        Attributes set on self:
            processor: Mock processor instance with fake poll_fn.
            mock_sm: Mock state machine created by create_mock_state_machine().
            ctx: Processing context for merge request iid 42 containing the mock state machine.
        """
        self.timed_out_outcome = PollOutcome(
            completed=False,
            timed_out=True,
            shutdown_requested=False,
            result=None,
        )

        async def fake_poll(config, check_fn, shutdown_event):
            return self.timed_out_outcome

        self.processor = create_mock_processor(poll_fn=fake_poll)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

    async def when_wait_for_rebase_quick_is_called(self):
        self.raised = None
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
