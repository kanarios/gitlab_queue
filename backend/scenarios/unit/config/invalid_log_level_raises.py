"""Test that _to_log_level raises ValueError on invalid input."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_log_level


class Scenario(vedro.Scenario):
    subject = "invalid log level raises ValueError"

    def given_invalid_log_level(self):
        self.invalid_value = "INVALID"

    def when_to_log_level_is_called(self):
        try:
            _to_log_level(self.invalid_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        assert self.raised is not None

    def and_message_contains_invalid_log_level(self):
        assert "Invalid log level" in str(self.raised)
