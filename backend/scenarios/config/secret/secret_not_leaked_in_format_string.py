"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret not leaked in format string"

    def given_secret(self):
        self.secret_value = "super-secret-api-key"
        self.secret = Secret(self.secret_value)

    def when_using_in_format_string(self):
        self.formatted = f"Token: {self.secret}"

    def then_value_should_be_hidden(self):
        assert self.secret_value not in self.formatted
        assert "***" in self.formatted
