"""Test _wait_for_rebase_quick raises GitLabConflictError on conflict.

When check_rebase_status returns has_conflicts=True during a quick rebase
wait, the method should raise GitLabConflictError to signal that the
rebase cannot proceed due to merge conflicts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError

from .._helpers import (
    create_mock_processor,
    create_mock_state_machine,
    create_processing_context,
)


class Scenario(vedro.Scenario):
    subject = "wait for rebase quick raises conflict error on conflict"

    def given_processor_with_conflicting_rebase(self):
        """
        Set up a mock processor, state machine, and processing context that simulate a merge request with a quick rebase conflict.

        Creates:
        - self.processor: mock processor
        - self.mock_sm: mock state machine
        - self.ctx: processing context for MR IID 42 linked to the mock state machine

        Configures the processor's GitLab client mocks to simulate a quick rebase that is not in progress but has conflicts:
        - check_rebase_status -> (False, True)
        - get_mr_conflicts -> []
        """
        self.processor = create_mock_processor()

        self.mock_sm = create_mock_state_machine()
        self.ctx = create_processing_context(mr_iid=42, state_machine=self.mock_sm)

        # check_rebase_status returns (not_in_progress, has_conflicts)
        self.processor.gitlab_client.check_rebase_status = AsyncMock(return_value=(False, True))
        self.processor.gitlab_client.get_mr_conflicts = AsyncMock(return_value=[])

    async def when_wait_for_rebase_quick_is_called(self):
        """
        Calls the processor's _wait_for_rebase_quick with the prepared context and captures any GitLabConflictError.

        If a GitLabConflictError is raised, stores the exception on self.raised; otherwise leaves self.raised as None.
        """
        self.raised = None
        try:
            await self.processor._rebase_handler.wait_for_rebase_quick(self.ctx)
        except GitLabConflictError as exc:
            self.raised = exc

    def then_conflict_error_is_raised(self):
        """
        Assert that the scenario captured a raised exception and that it is a GitLabConflictError.

        Raises:
            AssertionError: If no exception was captured or the captured exception is not a GitLabConflictError.
        """
        assert self.raised is not None
        assert isinstance(self.raised, GitLabConflictError)
