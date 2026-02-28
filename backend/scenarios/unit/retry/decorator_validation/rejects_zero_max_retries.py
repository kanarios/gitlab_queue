"""Test _create_async_retry_decorator raises ValueError for max_retries < 1."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.utils.retry import _create_async_retry_decorator


class Scenario(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError for max_retries=0"

    def given_invalid_max_retries(self):
        """
        Set the test parameter `max_retries` to 0 to represent an invalid retry count.
        """
        self.max_retries = 0

    def when_decorator_is_created(self):
        """
        Attempts to create the asynchronous retry decorator using the scenario's `max_retries` and captures any ValueError raised into `self.exc_info`.

        If `_create_async_retry_decorator` raises a ValueError, the exception information will be stored in `self.exc_info` for later assertions.
        """
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda _e: True,
                max_retries=self.max_retries,
                initial_wait=1.0,
                max_wait=10.0,
                jitter=1.0,
                operation_name="test",
            )

    def then_error_was_raised(self):
        """
        Asserts that the captured exception is a ValueError.

        Raises AssertionError if the stored exception type is not ValueError.
        """
        assert self.exc_info.type is ValueError

    def and_message_matches_expected_pattern(self):
        """
        Asserts that the captured ValueError message contains the expected "max_retries must be >= 1" substring.

        Raises:
                AssertionError: If the expected substring is not found in the captured exception message.
        """
        assert "max_retries must be >= 1" in str(self.exc_info.value)
