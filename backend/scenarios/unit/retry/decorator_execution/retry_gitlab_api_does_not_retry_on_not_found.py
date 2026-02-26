"""Test retry_gitlab_api raises immediately on a non-retryable GitLabNotFoundError."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabNotFoundError
from gitlab_queue.utils.retry import retry_gitlab_api


class Scenario(vedro.Scenario):
    subject = "retry_gitlab_api does not retry on GitLabNotFoundError"

    def given_decorated_function_that_raises_not_found(self):
        """
        Prepare a decorated asynchronous function that increments a call counter and always raises a GitLabNotFoundError.

        The method initializes self.call_count to 0, defines an async function decorated with retry_gitlab_api (max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0) which increments the counter and raises GitLabNotFoundError("Not found", status_code=404), and assigns that function to self.func for use in the scenario.
        """
        self.call_count = 0

        @retry_gitlab_api(max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0)
        async def not_found_function():
            """
            Increments self.call_count and raises a GitLabNotFoundError with status_code 404.

            Raises:
                GitLabNotFoundError: Always raised with message "Not found" and status_code=404.
            """
            self.call_count += 1
            raise GitLabNotFoundError("Not found", status_code=404)

        self.func = not_found_function

    async def when_function_is_called(self):
        """
        Executes the decorated function and captures any GitLabNotFoundError raised.

        If a GitLabNotFoundError is raised during execution, its exception info is stored on self.exc_info.
        """
        with catched(GitLabNotFoundError) as self.exc_info:
            await self.func()

    def then_not_found_error_was_raised(self):
        """
        Asserts that the captured exception is a GitLabNotFoundError.

        Raises:
            AssertionError: If the captured exception type is not `GitLabNotFoundError`.
        """
        assert self.exc_info.type is GitLabNotFoundError

    def and_function_was_called_only_once(self):
        """
        Asserts that the decorated function was invoked exactly once.

        Raises an AssertionError if the recorded call count is not equal to 1.
        """
        assert self.call_count == 1
