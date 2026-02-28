"""Test that _to_cors_origins_list raises ValueError on empty string."""

from __future__ import annotations

import vedro

from gitlab_queue.config import _to_cors_origins_list


class Scenario(vedro.Scenario):
    subject = "empty CORS origins raises ValueError"

    def given_empty_cors_origins(self):
        """
        Set the scenario's CORS origins input to an empty string.
        """
        self.empty_value = ""

    def when_to_cors_origins_list_is_called(self):
        """
        Call _to_cors_origins_list with the prepared empty input and store any ValueError on self.raised.

        If a ValueError is raised, its exception instance is assigned to self.raised; if no ValueError occurs, self.raised is set to None.
        """
        try:
            _to_cors_origins_list(self.empty_value)
            self.raised = None
        except ValueError as exc:
            self.raised = exc

    def then_value_error_is_raised(self):
        """
        Asserts that a ValueError was raised during the previous action.

        Raises an AssertionError if no exception was captured in self.raised.
        """
        assert self.raised is not None

    def and_message_contains_cannot_be_empty(self):
        """
        Asserts that the stored exception's message contains "CORS origins cannot be empty".

        Raises:
            AssertionError: if the exception message does not contain the required text.
        """
        assert "CORS origins cannot be empty" in str(self.raised)
