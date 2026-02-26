"""Test that _to_log_format raises ValueError on invalid input."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_log_format


class Scenario(vedro.Scenario):
    subject = "invalid log format raises ValueError"

    def given_invalid_log_format(self):
        """
        Set self.invalid_value to "xml" to represent an invalid log format for the scenario.
        """
        self.invalid_value = "xml"

    def when_to_log_format_is_called(self):
        """
        Call _to_log_format with the previously set invalid value and record any ValueError in self.raised.

        If a ValueError is raised, store the exception in self.raised; otherwise set self.raised to None.
        """
        try:
            _to_log_format(self.invalid_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        """
        Asserts that a ValueError was raised during the action step and was captured on the scenario.

        Raises:
                AssertionError: If no exception was captured (i.e., `self.raised` is `None`).
        """
        assert self.raised is not None

    def and_message_contains_invalid_log_format(self):
        """
        Asserts that the captured exception's message contains "Invalid log format".

        Verifies that a ValueError raised for an invalid log format includes the expected error text.
        """
        assert "Invalid log format" in str(self.raised)
