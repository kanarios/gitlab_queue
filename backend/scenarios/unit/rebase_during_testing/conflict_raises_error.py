"""Test scenario: GitLabConflictError during rebase is raised properly."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.core.rebase_during_testing import (
    RebaseDuringTestingContext,
    RebaseDuringTestingHandler,
)
from scenarios.fakes import FakeGitLabClient, create_mr

from ._helpers import MockSettings


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed raises GitLabConflictError when mr has conflicts"

    def given_handler_with_conflicting_mr(self):
        """
        Prepare a RebaseDuringTestingHandler and context configured with a FakeGitLabClient
        that reports a merge request with conflicts.
        """
        mr = create_mr(
            iid=42,
            has_conflicts=True,
            merge_status="cannot_be_merged",
            sha="abc123",
        )
        self.gitlab_client = FakeGitLabClient(mr_responses={42: mr})
        self.settings = MockSettings()
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
        Calls the handler's handle_rebase_if_needed and stores any GitLabConflictError raised.
        """
        self.raised_error = None
        try:
            await self.handler.handle_rebase_if_needed(42, self.ctx)
        except GitLabConflictError as e:
            self.raised_error = e

    def then_conflict_error_should_be_raised(self):
        assert self.raised_error is not None

    def and_error_message_should_mention_conflicts(self):
        assert "conflicts" in str(self.raised_error).lower()
