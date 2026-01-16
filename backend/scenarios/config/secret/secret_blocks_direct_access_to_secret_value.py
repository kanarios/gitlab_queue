"""Unit tests for Secret class."""

import vedro
from d42 import fake
from scenarios.schemas import SecretValueSchema

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "try to access secret value directly"

    def given_secret(self):
        self.secret = Secret(fake(SecretValueSchema))

    def when_trying_to_access_secret_value_directly(self):
        try:
            _ = self.secret._secret_value
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None
        assert "Direct access" in str(self.error) or "not allowed" in str(self.error)
