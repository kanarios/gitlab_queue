"""Test that _to_log_level raises ValueError on invalid input."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_log_level


class Scenario(vedro.Scenario):
    subject = "invalid log level raises ValueError"

    def given_invalid_log_level(self):
        """
        Set up an invalid log level value for the scenario.

        Assigns the string "INVALID" to self.invalid_value to simulate an unsupported log level.
        """
        self.invalid_value = "INVALID"

    def when_to_log_level_is_called(self):
        """
        Calls _to_log_level with the scenario's invalid_value and records any ValueError in self.raised.

        If a ValueError is raised it is stored in self.raised; if no error occurs, self.raised is set to None.
        """
        try:
            _to_log_level(self.invalid_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        """
        Asserts that a ValueError was captured during the action phase.

        Raises:
            AssertionError: if no ValueError was captured (i.e., self.raised is None).
        """
        assert self.raised is not None

    def and_message_contains_invalid_log_level(self):
        """
        Asserts that the captured exception's message contains the text "Invalid log level".

        Raises:
            AssertionError: If the exception message does not contain "Invalid log level".
        """
        assert "Invalid log level" in str(self.raised)
