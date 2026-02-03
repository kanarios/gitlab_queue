"""Test retry_gitlab_api raises immediately on a non-retryable GitLabNotFoundError."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.clients.gitlab import GitLabNotFoundError
from gitlab_queue.utils.retry import retry_gitlab_api


class Scenario(vedro.Scenario):
    subject = "retry_gitlab_api does not retry on GitLabNotFoundError"

    def given_decorated_function_that_raises_not_found(self):
        self.call_count = 0

        @retry_gitlab_api(max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0)
        async def not_found_function():
            self.call_count += 1
            raise GitLabNotFoundError("Not found", status_code=404)

        self.func = not_found_function

    async def when_function_is_called(self):
        with catched(GitLabNotFoundError) as self.exc_info:
            await self.func()

    def then_not_found_error_was_raised(self):
        assert self.exc_info.type is GitLabNotFoundError

    def and_function_was_called_only_once(self):
        assert self.call_count == 1
