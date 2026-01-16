"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "try to delete secret attribute"

    def given_secret(self):
        self.secret = Secret("test-value")

    def when_trying_to_delete_attribute(self):
        try:
            del self.secret.get_secret_value
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None
