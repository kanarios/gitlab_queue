"""Test retry_rebase raises immediately on a GitLabConflictError without retrying."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabConflictError
from gitlab_queue.utils.retry import retry_rebase


class Scenario(vedro.Scenario):
    subject = "retry_rebase does not retry on GitLabConflictError"

    def given_decorated_function_that_raises_conflict(self):
        """
        Prepare a decorated asynchronous function that always raises a GitLabConflictError.

        Sets self.call_count to 0, defines an async `rebase_operation` wrapped with `retry_rebase(max_retries=3, initial_wait=0.01, max_wait=0.02)` which increments `self.call_count` and raises `GitLabConflictError(status_code=409)`, and assigns the decorated function to `self.func`.
        """
        self.call_count = 0

        @retry_rebase(max_retries=3, initial_wait=0.01, max_wait=0.02)
        async def rebase_operation():
            """
            Simulates a rebase operation that records a call and raises a GitLabConflictError.

            Increments self.call_count and then raises GitLabConflictError with message "Merge conflict" and status_code 409 to emulate a merge conflict during testing.
            """
            self.call_count += 1
            raise GitLabConflictError("Merge conflict", status_code=409)

        self.func = rebase_operation

    async def when_function_is_called(self):
        """
        Calls the decorated async function and captures a GitLabConflictError raised by it.

        If a GitLabConflictError is raised during the call, the exception info is stored on self.exc_info for later assertions.
        """
        with catched(GitLabConflictError) as self.exc_info:
            await self.func()

    def then_conflict_error_was_raised(self):
        """
        Assert that the captured exception is a GitLabConflictError.

        Raises:
            AssertionError: If the captured exception type is not `GitLabConflictError`.
        """
        assert self.exc_info.type is GitLabConflictError

    def and_function_was_called_only_once(self):
        assert self.call_count == 1
