"""Test retry_gitlab_api retries the wrapped function on a GitLabServerError."""

from __future__ import annotations

import vedro

from gitlab_queue.clients.gitlab import GitLabServerError
from gitlab_queue.utils.retry import retry_gitlab_api


class Scenario(vedro.Scenario):
    subject = "retry_gitlab_api retries on server error"

    def given_decorated_function_that_fails_then_succeeds(self):
        self.call_count = 0

        @retry_gitlab_api(max_retries=3, initial_wait=0.01, max_wait=0.02, jitter=0)
        async def flaky_function():
            self.call_count += 1
            if self.call_count == 1:
                raise GitLabServerError("Server error", status_code=500)
            return "success"

        self.func = flaky_function

    async def when_function_is_called(self):
        self.result = await self.func()

    def then_function_was_retried(self):
        assert self.call_count == 2

    def and_result_is_success(self):
        assert self.result == "success"
