"""Test retry_rebase raises immediately on a GitLabConflictError without retrying."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.utils.retry import retry_rebase


class Scenario(vedro.Scenario):
    subject = "retry_rebase does not retry on GitLabConflictError"

    def given_decorated_function_that_raises_conflict(self):
        self.call_count = 0

        @retry_rebase(max_retries=3, initial_wait=0.01, max_wait=0.02)
        async def rebase_operation():
            self.call_count += 1
            raise GitLabConflictError("Merge conflict", status_code=409)

        self.func = rebase_operation

    async def when_function_is_called(self):
        with catched(GitLabConflictError) as self.exc_info:
            await self.func()

    def then_conflict_error_was_raised(self):
        assert self.exc_info.type is GitLabConflictError

    def and_function_was_called_only_once(self):
        assert self.call_count == 1
