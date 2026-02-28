"""Test retry_gitlab_api retries the wrapped function on a GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.utils.retry import retry_gitlab_api


class Scenario(vedro.Scenario):
    subject = "retry_gitlab_api retries on server error"

    def given_decorated_function_that_fails_then_succeeds(self):
        """
        Create and store a decorated async function that fails once with a GitLabServerError then succeeds.

        Initializes self.call_count to 0, defines an async function decorated with retry_gitlab_api(max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0) whose first invocation raises GitLabServerError("Server error", status_code=500) and subsequent invocations return "success", and saves the decorated function to self.func.
        """
        self.call_count = 0

        @retry_gitlab_api(max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0)
        async def flaky_function():
            """
            A flaky async helper that increments an instance call counter, raises a GitLabServerError on its first invocation, and returns "success" thereafter.

            Returns:
                str: The string "success" when the call does not raise.

            Raises:
                GitLabServerError: On the first invocation (when `self.call_count` becomes 1) with status_code 500.
            """
            self.call_count += 1
            if self.call_count == 1:
                raise GitLabServerError("Server error", status_code=500)
            return "success"

        self.func = flaky_function

    async def when_function_is_called(self):
        """
        Call the decorated async function and store its return value on the scenario as `self.result`.
        """
        self.result = await self.func()

    def then_function_was_retried(self):
        """
        Asserts that the decorated function was retried once by verifying it was called twice.

        Raises an AssertionError if the call count is not equal to 2.
        """
        assert self.call_count == 2

    def and_result_is_success(self):
        """
        Asserts that the scenario's result equals "success".

        Raises:
            AssertionError: If self.result is not "success".
        """
        assert self.result == "success"
