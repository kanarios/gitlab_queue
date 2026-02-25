"""Test that _to_cors_origins_list raises ValueError on empty string."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_cors_origins_list


class Scenario(vedro.Scenario):
    subject = "empty CORS origins raises ValueError"

    def given_empty_cors_origins(self):
        self.empty_value = ""

    def when_to_cors_origins_list_is_called(self):
        try:
            _to_cors_origins_list(self.empty_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        assert self.raised is not None

    def and_message_contains_cannot_be_empty(self):
        assert "CORS origins cannot be empty" in str(self.raised)
