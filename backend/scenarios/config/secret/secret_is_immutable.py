"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "secret is immutable"

    def given_secret(self):
        self.secret = Secret(fake(SecretValueSchema))

    def when_trying_to_set_attribute(self):
        try:
            self.secret.new_attr = "new-value"
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None
        assert "immutable" in str(self.error).lower()
