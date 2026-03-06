"""Test _wait_for_rebase_quick raises GitLabAPIError when shutdown requested during wait.

Line 1165: when shutdown event is set during quick rebase polling, raise GitLabAPIError.
"""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabAPIError

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait_for_rebase_quick raises GitLabAPIError when shutdown is requested"

    def given_processor_with_shutdown_during_quick_rebase(self):
        self.processor = create_mock_processor()

        # Rebase still in progress — would keep polling, but shutdown stops it
        self.processor.gitlab_client.rebase_status = (True, False)

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # Set shutdown BEFORE calling
        self.processor._shutdown_event.set()

    async def when_wait_for_rebase_quick_is_called(self):
        self.exception = None
        try:
            await self.processor._rebase_handler.wait_for_rebase_quick(self.ctx)
        except GitLabAPIError as e:
            self.exception = e

    def then_api_error_is_raised(self):
        assert self.exception is not None
        assert isinstance(self.exception, GitLabAPIError)

    def and_error_mentions_shutdown(self):
        assert "Shutdown" in str(self.exception) or "shutdown" in str(self.exception)
