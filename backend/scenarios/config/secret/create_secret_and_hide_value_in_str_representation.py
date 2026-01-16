"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "create secret and hide value in str representation"

    def given_secret_value(self):
        self.secret_value = "glpat-super-secret-token"

    def when_secret_is_created(self):
        self.secret = Secret(self.secret_value)

    def then_str_should_hide_value(self):
        assert str(self.secret) == "***"

    def and_repr_should_hide_value(self):
        assert "***" in repr(self.secret)
        assert self.secret_value not in repr(self.secret)
