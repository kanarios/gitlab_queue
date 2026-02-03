"""Test _create_async_retry_decorator raises ValueError when initial_wait > max_wait."""

from __future__ import annotations

import vedro
from vedro import catched

from gitlab_queue.utils.retry import _create_async_retry_decorator


class Scenario(vedro.Scenario):
    subject = "_create_async_retry_decorator raises ValueError when initial_wait > max_wait"

    def given_initial_wait_exceeds_max_wait(self):
        self.initial_wait = 10.0
        self.max_wait = 5.0

    def when_decorator_is_created(self):
        with catched(ValueError) as self.exc_info:
            _create_async_retry_decorator(
                retry_predicate=lambda e: True,
                max_retries=3,
                initial_wait=self.initial_wait,
                max_wait=self.max_wait,
                jitter=1.0,
                operation_name="test",
            )

    def then_error_was_raised(self):
        assert self.exc_info.type is ValueError

    def and_message_matches_expected_pattern(self):
        assert "initial_wait" in str(self.exc_info.value)
        assert "cannot exceed max_wait" in str(self.exc_info.value)
