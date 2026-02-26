"""Test _create_async_retry_decorator raises ValueError when initial_wait > max_wait."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.utils.retry import _create_async_retry_decorator


class Scenario(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError when initial_wait > max_wait"

    def given_initial_wait_exceeds_max_wait(self):
        """
        Set up test inputs with initial_wait = 10.0 and max_wait = 5.0 so initial_wait exceeds max_wait.

        Prepares the scenario for validating that creating the retry decorator raises a ValueError when the initial wait time is greater than the maximum wait time.
        """
        self.initial_wait = 10.0
        self.max_wait = 5.0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda _e: True,
                max_retries=3,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=1.0,
                operation_name="test",
            )

    def then_error_was_raised(self):
        """
        Asserts that the captured exception is a ValueError.

        Raises an AssertionError if no exception was captured or if the captured exception type is not ValueError.
        """
        assert self.exc_info.type is ValueError

    def and_message_matches_expected_pattern(self):
        """
        Asserts that the captured ValueError message contains the substrings "initial_wait" and "cannot exceed max_wait".

        This ensures the raised exception reports that the initial wait value is invalid because it exceeds the configured maximum wait.
        """
        assert "initial_wait" in str(self.exc_info.value)
        assert "cannot exceed max_wait" in str(self.exc_info.value)
