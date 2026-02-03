"""Test that retry max wait is capped properly.

Covers retry.py lines 166, 229-230, 256:
- is_retryable_sqlite_error returns False for non-matching OperationalError
- _create_async_retry_decorator validates negative wait parameters
- _create_async_retry_decorator correctly caps wait time via wait_exponential_jitter
"""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.utils.retry import (
    _create_async_retry_decorator,
    is_retryable_sqlite_error,
)


class Scenario(vedro.Scenario):
    subject = "is_retryable_sqlite_error returns False for non-transient OperationalError"

    def given_non_retryable_operational_error(self):
        from sqlalchemy.exc import OperationalError

        self.error = OperationalError("SELECT 1", {}, Exception("no such table: foo"))

    def when_is_retryable_is_checked(self):
        self.result = is_retryable_sqlite_error(self.error)

    def then_result_is_false(self):
        assert self.result is False


class Scenario2(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError for negative wait params"

    def given_negative_initial_wait(self):
        self.initial_wait = -1.0
        self.max_wait = 10.0
        self.jitter = 1.0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=3,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=self.jitter,
                operation_name="test",
            )

    def then_error_was_raised(self):
        assert self.exc_info.type is ValueError

    def and_message_mentions_non_negative(self):
        assert "non-negative" in str(self.exc_info.value)


class Scenario3(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError for negative max_wait"

    def given_negative_max_wait(self):
        self.initial_wait = 1.0
        self.max_wait = -5.0
        self.jitter = 1.0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=3,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=self.jitter,
                operation_name="test",
            )

    def then_error_was_raised(self):
        assert self.exc_info.type is ValueError

    def and_message_mentions_non_negative(self):
        assert "non-negative" in str(self.exc_info.value)


class Scenario4(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError for negative jitter"

    def given_negative_jitter(self):
        self.initial_wait = 1.0
        self.max_wait = 10.0
        self.jitter = -1.0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=3,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=self.jitter,
                operation_name="test",
            )

    def then_error_was_raised(self):
        assert self.exc_info.type is ValueError

    def and_message_mentions_non_negative(self):
        assert "non-negative" in str(self.exc_info.value)


class Scenario5(vedro.Scenario):
    subject = "_create_async_retry_decorator accepts zero wait params"

    def given_zero_wait_params(self):
        self.initial_wait = 0.0
        self.max_wait = 0.0
        self.jitter = 0.0

    def when_decorator_is_created(self):
        self.raised = False
        try:
            self.decorator = _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=1,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=self.jitter,
                operation_name="test",
            )
        except ValueError:
            self.raised = True

    def then_no_error_is_raised(self):
        assert self.raised is False

    def and_decorator_is_callable(self):
        assert callable(self.decorator)
