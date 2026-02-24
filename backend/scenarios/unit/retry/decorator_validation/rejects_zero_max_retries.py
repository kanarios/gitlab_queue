"""Test _create_async_retry_decorator raises ValueError for max_retries < 1."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.utils.retry import _create_async_retry_decorator


class Scenario(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError for max_retries=0"

    def given_invalid_max_retries(self):
        self.max_retries = 0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=self.max_retries,
                initial_wait=1.0,
                max_wait=10.0,
                jitter=1.0,
                operation_name="test",
            )

    def then_error_was_raised(self):
        assert self.exc_info.type is ValueError

    def and_message_matches_expected_pattern(self):
        assert "max_retries must be >= 1" in str(self.exc_info.value)
