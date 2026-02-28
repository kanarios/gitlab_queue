"""Test scenario: GitLabConflictError during rebase is raised properly."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)


def create_mock_settings() -> MagicMock:
    """
    Create a MagicMock that mimics settings used by the rebase handler in tests.

    The mock includes the following attributes with typical test values:
    - rebase_timeout_seconds: 60
    - pipeline_poll_interval_seconds: 5
    - post_rebase_pipeline_wait_seconds: 60

    Returns:
        MagicMock: A mock settings object configured with the above attributes.
    """
    settings = MagicMock()
    settings.rebase_timeout_seconds = 60
    settings.pipeline_poll_interval_seconds = 5
    settings.post_rebase_pipeline_wait_seconds = 60
    return settings


def create_mock_gitlab_client_with_conflicts() -> MagicMock:
    """
    Create a MagicMock GitLab client whose `get_mr` returns a merge request mock that indicates merge conflicts.

    Returns:
        MagicMock: Mocked GitLab client with an async `get_mr` method that returns an MR object where
            `has_conflicts` is True, `merge_status` is "cannot_be_merged", and `sha` is "abc123".
    """
    client = MagicMock()
    mr = MagicMock()
    mr.has_conflicts = True
    mr.merge_status = "cannot_be_merged"
    mr.sha = "abc123"
    client.get_mr = AsyncMock(return_value=mr)
    return client


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed raises GitLabConflictError when mr has conflicts"

    def given_handler_with_conflicting_mr(self):
        """
        Prepare a RebaseDuringTestingHandler and context configured with a mocked GitLab client that reports a merge request with conflicts.

        This sets self.gitlab_client to a mock that returns an MR exhibiting conflicts, self.settings to test settings, self.handler to a RebaseDuringTestingHandler using those mocks, and self.ctx to a RebaseDuringTestingContext initialized for the rebase test.
        """
        self.gitlab_client = create_mock_gitlab_client_with_conflicts()
        self.settings = create_mock_settings()
        self.handler = RebaseDuringTestingHandler(
            gitlab_client=self.gitlab_client,
            settings=self.settings,
        )
        self.ctx = RebaseDuringTestingContext(
            rebase_count=0,
            max_attempts=3,
            current_pipeline_id=100,
        )

    async def when_handle_rebase_if_needed_is_called(self):
        """
        Calls the handler's handle_rebase_if_needed and stores any GitLabConflictError raised in self.raised_error.

        If a GitLabConflictError occurs, it is caught and assigned to self.raised_error; otherwise self.raised_error is left as None.
        """
        self.raised_error = None
        try:
            await self.handler.handle_rebase_if_needed(42, self.ctx)
        except GitLabConflictError as e:
            self.raised_error = e

    def then_conflict_error_should_be_raised(self):
        """
        Asserts that the scenario captured a GitLabConflictError.

        Verifies that self.raised_error is not None and that it is an instance of GitLabConflictError; if the check fails, an AssertionError is raised indicating the actual type.
        """
        assert self.raised_error is not None
        assert isinstance(self.raised_error, GitLabConflictError), (
            f"Expected GitLabConflictError, got {type(self.raised_error)}"
        )

    def and_error_message_should_mention_conflicts(self):
        """
        Asserts that the captured error's message contains the word "conflicts".

        Raises:
            AssertionError: If the error message does not include "conflicts" (case-insensitive).
        """
        assert "conflicts" in str(self.raised_error).lower(), (
            f"Expected error message to mention conflicts, got: {self.raised_error}"
        )
