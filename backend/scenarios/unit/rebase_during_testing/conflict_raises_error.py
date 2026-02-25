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
    """Create mock Settings for rebase handler tests."""
    settings = MagicMock()
    settings.rebase_timeout_seconds = 60
    settings.pipeline_poll_interval_seconds = 5
    settings.post_rebase_pipeline_wait_seconds = 60
    return settings


def create_mock_gitlab_client_with_conflicts() -> MagicMock:
    """Create mock GitLabClient that reports conflicts on check_needs_rebase."""
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
        self.raised_error = None
        try:
            await self.handler.handle_rebase_if_needed(42, self.ctx)
        except GitLabConflictError as e:
            self.raised_error = e

    def then_conflict_error_should_be_raised(self):
        assert self.raised_error is not None
        assert isinstance(self.raised_error, GitLabConflictError), (
            f"Expected GitLabConflictError, got {type(self.raised_error)}"
        )

    def and_error_message_should_mention_conflicts(self):
        assert "conflicts" in str(self.raised_error).lower(), (
            f"Expected error message to mention conflicts, got: {self.raised_error}"
        )
