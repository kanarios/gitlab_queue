"""Test that _to_log_format raises ValueError on invalid input."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_log_format


class Scenario(vedro.Scenario):
    subject = "invalid log format raises ValueError"

    def given_invalid_log_format(self):
        self.invalid_value = "xml"

    def when_to_log_format_is_called(self):
        try:
            _to_log_format(self.invalid_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        assert self.raised is not None

    def and_message_contains_invalid_log_format(self):
        assert "Invalid log format" in str(self.raised)
