"""Test retry_sqlite retries the wrapped function on an OperationalError database lock."""

from __future__ import annotations

import vedro
from sqlalchemy.exc import OperationalError

from gitlab_queue.utils.retry import retry_sqlite


class Scenario(vedro.Scenario):
    subject = "retry_sqlite retries on database is locked error"

    def given_decorated_function_that_fails_then_succeeds(self):
        self.call_count = 0

        @retry_sqlite(max_retries=3, initial_wait=0.01, max_wait=0.02)
        async def db_operation():
            self.call_count += 1
            if self.call_count == 1:
                raise OperationalError("", {}, Exception("database is locked"))
            return "saved"

        self.func = db_operation

    async def when_function_is_called(self):
        self.result = await self.func()

    def then_function_was_retried(self):
        assert self.call_count == 2

    def and_result_is_saved(self):
        assert self.result == "saved"
