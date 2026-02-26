"""Test retry_sqlite retries the wrapped function on an OperationalError database lock."""

from __future__ import annotations

import vedro
from sqlalchemy.exc import OperationalError

from gitlab_queue.utils.retry import retry_sqlite


class Scenario(vedro.Scenario):
    subject = "retry_sqlite retries on database is locked error"

    def given_decorated_function_that_fails_then_succeeds(self):
        """
        Create and store an async function decorated with retry_sqlite that fails once with a locked-database OperationalError and then succeeds.

        The method initializes self.call_count to 0 and defines an async db_operation wrapped by retry_sqlite (max_retries=3, initial_wait=0.01, max_wait=0.02). On its first invocation db_operation raises an OperationalError simulating "database is locked"; on subsequent invocations it returns "saved". The decorated function is assigned to self.func for later use in the scenario.
        """
        self.call_count = 0

        @retry_sqlite(max_retries=3, initial_wait=0.01, max_wait=0.02)
        async def db_operation():
            """
            Simulates a database operation that fails with an OperationalError on the first call and returns a success marker on subsequent calls.

            Increments self.call_count each time it's invoked; when self.call_count equals 1 it raises an OperationalError to simulate a locked database, otherwise it returns a success value.

            Returns:
                str: The string "saved" on successful attempts.

            Raises:
                sqlalchemy.exc.OperationalError: On the first invocation to simulate a database lock.
            """
            self.call_count += 1
            if self.call_count == 1:
                raise OperationalError("", {}, Exception("database is locked"))
            return "saved"

        self.func = db_operation

    async def when_function_is_called(self):
        """
        Invoke the decorated database operation and store its result on the scenario instance.

        Stores the awaited return value in `self.result`.
        """
        self.result = await self.func()

    def then_function_was_retried(self):
        """
        Assert that the decorated function was retried once.

        Checks that `self.call_count` equals 2, confirming the function was invoked initially and retried one additional time.
        """
        assert self.call_count == 2

    def and_result_is_saved(self):
        """
        Asserts that the operation returned the expected "saved" result.

        Raises:
            AssertionError: If self.result is not equal to "saved".
        """
        assert self.result == "saved"
