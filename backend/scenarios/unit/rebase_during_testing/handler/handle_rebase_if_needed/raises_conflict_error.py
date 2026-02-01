"""Test handle_rebase_if_needed raises GitLabConflictError when HAS_CONFLICTS."""

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabConflictError

from ..._helpers import (
    MockMergeRequest,
    create_context,
    create_handler,
    create_mock_gitlab_client,
)


class Scenario(vedro.Scenario):
    subject = "handle_rebase_if_needed raises GitLabConflictError when HAS_CONFLICTS"

    def given_handler_with_conflicting_mr(self):
        mr = MockMergeRequest(has_conflicts=True)
        self.client = create_mock_gitlab_client(mr=mr)
        self.handler = create_handler(gitlab_client=self.client)
        self.ctx = create_context()

    async def when_handle_rebase_if_needed_is_called(self):
        with catched(GitLabConflictError) as self.exception:
            await self.handler.handle_rebase_if_needed(42, self.ctx)

    def then_gitlab_conflict_error_is_raised(self):
        assert self.exception.type is GitLabConflictError

    def and_error_message_contains_conflicts(self):
        assert "conflicts" in str(self.exception.value).lower()
